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
from k8s.models.common import ObjectMeta
from k8s.models.service_account import ServiceAccount

from fiaas_deploy_daemon.deployer.kubernetes.owner_references import OwnerReferences
from fiaas_deploy_daemon.retry import retry_on_upsert_conflict
from fiaas_deploy_daemon.specs.models import AppSpec
from fiaas_deploy_daemon.tools import merge_dicts

LOG = logging.getLogger(__name__)


class ServiceAccountDeployer(object):
    def __init__(self, config, owner_references):
        self._owner_references: OwnerReferences = owner_references

    def deploy(self, app_spec: AppSpec, labels):
        self._create(app_spec, labels)

    @retry_on_upsert_conflict
    def _create(self, app_spec: AppSpec, labels):
        LOG.info("Creating/updating serviceAccount for %s with labels: %s", app_spec.name, labels)
        service_account_name = app_spec.name
        namespace = app_spec.namespace

        custom_annotations = {}
        custom_labels = labels
        custom_labels = merge_dicts(app_spec.labels.service_account, custom_labels)
        custom_annotations = merge_dicts(app_spec.annotations.service_account, custom_annotations)
        metadata = ObjectMeta(
            name=service_account_name, namespace=namespace, labels=custom_labels, annotations=custom_annotations
        )
        try:
            service_account = ServiceAccount.get(service_account_name, namespace)
            if not self._owned_by_fiaas(service_account):
                LOG.info("Found serviceAccount %s not managed by us.", service_account_name)
                LOG.info(
                    "Aborting the creation of a serviceAccount for Application: %s with labels: %s",
                    service_account_name,
                    labels,
                )
                return
        except NotFound:
            service_account = ServiceAccount()

        image_pull_secrets = []
        try:
            default_service_account = ServiceAccount.get("default", namespace)
            image_pull_secrets = default_service_account.imagePullSecrets
        except NotFound:
            LOG.info("No default service account found in namespace: %s", namespace)

        service_account.metadata = metadata
        service_account.imagePullSecrets = image_pull_secrets
        self._owner_references.apply(service_account, app_spec)
        service_account.save()

    def _owned_by_fiaas(self, service_account):
        return any(
            ref.apiVersion == "fiaas.schibsted.io/v1" and ref.kind == "Application"
            for ref in service_account.metadata.ownerReferences
        )
