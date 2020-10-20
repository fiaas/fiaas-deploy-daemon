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
from k8s.models.service_account import ServiceAccount

from k8s.models.common import ObjectMeta
from fiaas_deploy_daemon.retry import retry_on_upsert_conflict
from fiaas_deploy_daemon.tools import merge_dicts


LOG = logging.getLogger(__name__)


class ServiceAccountDeployer(object):
    def __init__(self, config, owner_references):
        self._owner_references = owner_references

    def deploy(self, app_spec, labels):
        self._create(app_spec, labels)

    def delete(self, app_spec):
        LOG.info("Deleting serviceAccount for %s", app_spec.name)
        try:
            service_account = ServiceAccount.get(app_spec.name, app_spec.namespace)
            if not self._owned_by_fiaas(service_account):
                return
            ServiceAccount.delete(app_spec.name, app_spec.namespace)
        except NotFound:
            pass

    @retry_on_upsert_conflict
    def _create(self, app_spec, labels):
        LOG.info("Creating/updating serviceAccount for %s with labels: %s", app_spec.name, labels)
        image_pull_secrets = []
        try:
            service_account = ServiceAccount.get(app_spec.name, app_spec.namespace)
            if not self._owned_by_fiaas(service_account):
                LOG.info("Found serviceAccount %s not managed by us.", app_spec.name)
                LOG.info("Aborting the creation of a serviceAccount for Application: %s with labels: %s", app_spec.name, labels)
                return
        except NotFound:
            pass

        try:
            default_service_account = ServiceAccount.get("default", app_spec.namespace)
            image_pull_secrets = default_service_account.imagePullSecrets
        except NotFound:
            LOG.info("No default service account found in namespace: %s", app_spec.namespace)
            pass
        service_account_name = app_spec.name
        custom_labels = labels
        custom_annotations = {}
        custom_labels = merge_dicts(app_spec.labels.service_account, custom_labels)
        custom_annotations = merge_dicts(app_spec.annotations.service_account, custom_annotations)
        metadata = ObjectMeta(name=service_account_name, namespace=app_spec.namespace, labels=custom_labels, annotations=custom_annotations)
        service_account = ServiceAccount.get_or_create(
                metadata=metadata,
                imagePullSecrets=image_pull_secrets
        )
        self._owner_references.apply(service_account, app_spec)
        service_account.save()

    def _owned_by_fiaas(self, service_account):
        return any(
                ref.apiVersion == 'fiaas.schibsted.io/v1' and ref.kind == 'Application' for ref in service_account.metadata.ownerReferences
        )
