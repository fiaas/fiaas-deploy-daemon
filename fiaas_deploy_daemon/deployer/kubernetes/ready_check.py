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
from k8s.models.deployment import Deployment
from monotonic import monotonic as time_monotonic

LOG = logging.getLogger(__name__)

FAIL_LIMIT_MULTIPLIER = 10


class ReadyCheck(object):
    def __init__(self, app_spec, bookkeeper, lifecycle, lifecycle_subject):
        self._app_spec = app_spec
        self._bookkeeper = bookkeeper
        self._lifecycle = lifecycle
        self._lifecycle_subject = lifecycle_subject
        self._fail_after_seconds = FAIL_LIMIT_MULTIPLIER * app_spec.replicas * app_spec.health_checks.readiness.initial_delay_seconds
        self._fail_after = time_monotonic() + self._fail_after_seconds

    def __call__(self):
        if self._ready():
            self._lifecycle.success(self._lifecycle_subject)
            self._bookkeeper.success(self._app_spec)
            return False
        if time_monotonic() >= self._fail_after:
            self._lifecycle.failed(self._lifecycle_subject)
            self._bookkeeper.failed(self._app_spec)
            LOG.error("Timed out after %d seconds waiting for %s to become ready",
                      self._fail_after_seconds, self._app_spec.name)
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
