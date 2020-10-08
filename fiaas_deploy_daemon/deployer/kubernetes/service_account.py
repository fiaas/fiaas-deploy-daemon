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
from k8s.models.common import ObjectMeta, LocalObjectReference
from k8s.models.service_account import ServiceAccount

from fiaas_deploy_daemon.retry import retry_on_upsert_conflict
from fiaas_deploy_daemon.tools import merge_dicts


LOG = logging.getLogger(__name__)


class ServiceAccountDeployer(object):
    def __init__(self, config, owner_references):
        self._owner_references = owner_references

    def deploy(self, app_spec, selector, labels):
        self._create(app_spec, labels)

    def delete(self, app_spec):
        LOG.info("Deleting serviceAccount for %s", app_spec.name)
        try:
            ServiceAccount.delete(app_spec.name, app_spec.namespace)
        except NotFound:
            pass

    @retry_on_upsert_conflict
    def _create(self, app_spec, labels):
        LOG.info("Creating/updating serviceAccount for %s with labels: %s", app_spec.name, labels)
        secrets = []
        image_pull_secrets = []
        automount_service_account_token = True
        try:
            service_account = ServiceAccount.get(app_spec.name, app_spec.namespace)
            image_pull_secrets = service_account.imagePullSecrets
            secrets = service_account.secrets
            automount_service_account_token = service_account.automountServiceAccountToken
        except NotFound:
            pass
        service_account_name = app_spec.name
        custom_labels = labels
        custom_annotations = {}
        if "service_account" in app_spec.labels:
            custom_labels = merge_dicts(app_spec.labels.service_account, custom_labels)
        if "service_account" in app_spec.annotations:
            custom_annotations = merge_dicts(app_spec.annotations.service_account, custom_annotations)
        metadata = ObjectMeta(name=service_account_name, namespace=app_spec.namespace, labels=custom_labels, annotations=custom_annotations)
        service_account = ServiceAccount.get_or_create(
                metadata=metadata,
                imagePullSecrets=image_pull_secrets,
                secrets=secrets,
                automountServiceAccountToken=automount_service_account_token
            )
        self._owner_references.apply(service_account, app_spec)
        service_account.save()
