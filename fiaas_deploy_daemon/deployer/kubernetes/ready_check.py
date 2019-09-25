#!/usr/bin/env python
# -*- coding: utf-8

from k8s.client import NotFound
from k8s.models.deployment import Deployment
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
from monotonic import monotonic as time_monotonic

FAIL_LIMIT_MULTIPLIER = 10


class ReadyCheck(object):
    def __init__(self, app_spec, bookkeeper, lifecycle):
        self._app_spec = app_spec
        self._bookkeeper = bookkeeper
        self._lifecycle = lifecycle
        fail_after_seconds = FAIL_LIMIT_MULTIPLIER * app_spec.replicas * app_spec.health_checks.readiness.initial_delay_seconds
        self._fail_after = time_monotonic() + fail_after_seconds

    def __call__(self):
        repository = _repository(self._app_spec)
        if self._ready():
            self._lifecycle.success(app_name=self._app_spec.name, namespace=self._app_spec.namespace,
                                    deployment_id=self._app_spec.deployment_id, repository=repository)
            self._bookkeeper.success(self._app_spec)
            return False
        if time_monotonic() >= self._fail_after:
            self._lifecycle.failed(app_name=self._app_spec.name, namespace=self._app_spec.namespace,
                                   deployment_id=self._app_spec.deployment_id, repository=repository)
            self._bookkeeper.failed(self._app_spec)
            return False
        return True

    def _ready(self):
        try:
            dep = Deployment.get(self._app_spec.name, self._app_spec.namespace)
        except NotFound:
            return False
        return (dep.status.updatedReplicas >= dep.spec.replicas and
                dep.status.availableReplicas >= dep.spec.replicas)

    def __eq__(self, other):
        return other._app_spec == self._app_spec and other._bookkeeper == self._bookkeeper \
               and other._lifecycle == self._lifecycle


def _repository(app_spec):
    try:
        return app_spec.annotations.deployment["fiaas/source-repository"]
    except (TypeError, KeyError, AttributeError):
        pass
