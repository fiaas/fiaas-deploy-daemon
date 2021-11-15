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
from __future__ import absolute_import

import logging

from k8s.client import NotFound
from k8s.models.pod_disruption_budget import PodDisruptionBudget, PodDisruptionBudgetSpec
from k8s.models.common import ObjectMeta

from fiaas_deploy_daemon.retry import retry_on_upsert_conflict
from fiaas_deploy_daemon.tools import merge_dicts

LOG = logging.getLogger(__name__)


class PodDisruptionBudgetDeployer(object):
    def __init__(self, owner_references, extension_hook):
        self._owner_references = owner_references
        self._extension_hook = extension_hook

    @retry_on_upsert_conflict
    def deploy(self, app_spec, labels):
        if should_have_pdb(app_spec):
            LOG.info("Creating/updating pod disruption budget for %s", app_spec.name)
            custom_labels = merge_dicts(app_spec.labels.horizontal_pod_autoscaler, labels)
            metadata = ObjectMeta(name=app_spec.name, namespace=app_spec.namespace, labels=custom_labels,
                                  annotations=app_spec.annotations.pod_disruption_budget)
            if app_spec.autoscaler.max_replicas == 1:
                spec = PodDisruptionBudgetSpec(maxUnavailable=1)
            else:
                spec = PodDisruptionBudgetSpec(minAvailable=app_spec.autoscaler.min_replicas)
            pdb = PodDisruptionBudget.get_or_create(metadata=metadata, spec=spec)
            self._owner_references.apply(pdb, app_spec)
            self._extension_hook.apply(pdb, app_spec)
            pdb.save()
        else:
            try:
                LOG.info("Deleting any pre-existing pod disruption budget for %s", app_spec.name)
                PodDisruptionBudget.delete(app_spec.name, app_spec.namespace)
            except NotFound:
                pass

    def delete(self, app_spec):
        LOG.info("Deleting pod disruption budget for %s", app_spec.name)
        try:
            PodDisruptionBudget.delete(app_spec.name, app_spec.namespace)
        except NotFound:
            pass


def should_have_pdb(app_spec):
    if not _autoscaler_enabled(app_spec.autoscaler):
        return False
    if not _enough_replicas_wanted(app_spec):
        LOG.warn("Can't enable autoscaler for %s with only %d max replicas", app_spec.name, app_spec.autoscaler.max_replicas)
        return False
    return True


def _autoscaler_enabled(autoscaler):
    return autoscaler.enabled


def _enough_replicas_wanted(app_spec):
    return app_spec.autoscaler.max_replicas > 1


def _request_cpu_is_set(app_spec):
    return app_spec.resources.requests.cpu is not None
