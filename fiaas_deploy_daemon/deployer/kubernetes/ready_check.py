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
from k8s.models.custom_resource_definition import CustomResourceDefinition
from k8s.models.deployment import Deployment
from k8s.models.ingress import Ingress
from monotonic import monotonic as time_monotonic

LOG = logging.getLogger(__name__)


class ReadyCheck(object):
    def __init__(self, app_spec, bookkeeper, lifecycle, lifecycle_subject, config):
        self._app_spec = app_spec
        self._bookkeeper = bookkeeper
        self._lifecycle = lifecycle
        self._lifecycle_subject = lifecycle_subject
        self._fail_after_seconds = _calculate_fail_time(
            config.ready_check_timeout_multiplier,
            app_spec.autoscaler.max_replicas,
            app_spec.health_checks.readiness.initial_delay_seconds
        )
        self._fail_after = time_monotonic() + self._fail_after_seconds
        self._should_check_ingress = config.tls_certificate_ready

    def __call__(self):
        if self._ready():
            self._lifecycle.success(self._lifecycle_subject)
            self._bookkeeper.success(self._app_spec)
            return False
        if time_monotonic() >= self._fail_after:
            LOG.error("Timed out after %d seconds waiting for %s to become ready",
                      self._fail_after_seconds, self._app_spec.name)
            self._lifecycle.failed(self._lifecycle_subject)
            self._bookkeeper.failed(self._app_spec)
            return False
        return True

    def _deployment_ready(self):
        try:
            dep = Deployment.get(self._app_spec.name, self._app_spec.namespace)
        except NotFound:
            return False
        expected_value = dep.spec.replicas if dep.spec.replicas > 0 else None

        return (dep.status.updatedReplicas == expected_value and
                dep.status.replicas == expected_value and
                dep.status.availableReplicas == expected_value and
                dep.status.observedGeneration >= dep.metadata.generation)

    def _is_certificate_ready(self, cert):
        for condition in cert.status.conditions:
            if condition.type == "Ready":
                return condition.status == "True"
        return False

    def _ingress_ready(self):
        try:
            ing_list = Ingress.find(self._app_spec.name, self._app_spec.namespace)
        except NotFound:
            return False

        for ingress in ing_list:
            if ingress.spec.tls:
                for tls_item in ingress.spec.tls:
                    try:
                        cert = CustomResourceDefinition.get(tls_item.secretName, ingress.metadata.namespace)
                    except NotFound:
                        return False
                    if not self._is_certificate_ready(cert):
                        return False

        return True

    def _ready(self):
        if not self._should_check_ingress or not self._app_spec.ingress_tls.enabled:
            return self._deployment_ready()

        return self._deployment_ready() and self._ingress_ready()

    def __eq__(self, other):
        return other._app_spec == self._app_spec and other._bookkeeper == self._bookkeeper \
               and other._lifecycle == self._lifecycle


def _calculate_fail_time(time_out, replicas, delay_seconds):
    return time_out*delay_seconds if replicas == 0 else time_out*delay_seconds*replicas
