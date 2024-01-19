#!/usr/bin/env python
# -*- coding: utf-8

# Copyright 2017-2019 The FIAAS Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import logging

from k8s.client import NotFound
from k8s.models.common import ObjectMeta, LabelSelector
from k8s.models.policy_v1_pod_disruption_budget import PodDisruptionBudget, PodDisruptionBudgetSpec

from fiaas_deploy_daemon.retry import retry_on_upsert_conflict
from fiaas_deploy_daemon.specs.models import AppSpec
from fiaas_deploy_daemon.tools import merge_dicts

LOG = logging.getLogger(__name__)


class PodDisruptionBudgetDeployer(object):
    def __init__(self, owner_references, extension_hook):
        self._owner_references = owner_references
        self._extension_hook = extension_hook

    @retry_on_upsert_conflict
    def deploy(self, app_spec: AppSpec, selector: dict[str, any], labels: dict[str, any]):
        if app_spec.autoscaler.min_replicas == 1 or app_spec.autoscaler.max_replicas == 1:
            return

        custom_annotations = {}
        custom_labels = labels
        custom_labels = merge_dicts(app_spec.labels.pod_disruption_budget, custom_labels)
        custom_annotations = merge_dicts(app_spec.annotations.pod_disruption_budget, custom_annotations)
        metadata = ObjectMeta(
            name=app_spec.name, namespace=app_spec.namespace, labels=custom_labels, annotations=custom_annotations
        )

        # Conservative default to ensure that we don't block evictions.
        # See https://github.com/fiaas/fiaas-deploy-daemon/issues/220 for discussion.
        max_unavailable = 1
        spec = PodDisruptionBudgetSpec(
            selector=LabelSelector(matchLabels=selector),
            maxUnavailable=max_unavailable
        )

        pdb = PodDisruptionBudget.get_or_create(metadata=metadata, spec=spec)

        self._owner_references.apply(pdb, app_spec)
        self._extension_hook.apply(pdb, app_spec)
        pdb.save()

    def delete(self, app_spec):
        LOG.info("Deleting podDisruptionBudget for %s", app_spec.name)
        try:
            PodDisruptionBudget.delete(app_spec.name, app_spec.namespace)
        except NotFound:
            pass
