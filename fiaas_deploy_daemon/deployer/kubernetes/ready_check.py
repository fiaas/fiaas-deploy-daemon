#!/usr/bin/env python
# -*- coding: utf-8

from monotonic import monotonic as time_monotonic

from k8s.models.deployment import Deployment
from k8s.client import NotFound

FAIL_LIMIT_MULTIPLIER = 10


class ReadyCheck(object):
    def __init__(self, app_spec, bookkeeper):
        self._app_spec = app_spec
        self._bookkeeper = bookkeeper
        fail_after_seconds = FAIL_LIMIT_MULTIPLIER * app_spec.replicas * app_spec.health_checks.readiness.initial_delay_seconds
        self._fail_after = time_monotonic() + fail_after_seconds

    def __call__(self):
        if self._ready():
            self._bookkeeper.success(self._app_spec)
            return False
        if time_monotonic() >= self._fail_after:
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
        return other._app_spec == self._app_spec and other._bookkeeper == self._bookkeeper
