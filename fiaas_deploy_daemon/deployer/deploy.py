#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import logging

from blinker import signal
from prometheus_client import Counter, Histogram

from ..base_thread import DaemonThread

LOG = logging.getLogger(__name__)


class Deployer(DaemonThread):
    """Take incoming AppSpecs and use the framework-adapter to deploy the app

    Mainly focused on bookkeeping, and leaving the hard work to the framework-adapter.
    """
    def __init__(self, deploy_queue, adapter):
        super(Deployer, self).__init__()
        self._queue = _make_gen(deploy_queue.get)
        self._bookkeeper = _Bookkeeper()
        self._adapter = adapter

    def __call__(self):
        for app_spec in self._queue:
            LOG.info("Received %r for deployment", app_spec)
            try:
                with self._bookkeeper.time(app_spec):
                    self._adapter.deploy(app_spec)
                self._bookkeeper.success(app_spec)
            except Exception:
                self._bookkeeper.failed(app_spec)
                LOG.exception("Error while deploying: ")


class _Bookkeeper(object):
    """Trigger signals and counters"""
    deploy_counter = Counter("deployer_requests", "Request to depoy an app")
    deploy_signal = signal("deploy_started", "Signals start of deployment")
    error_counter = Counter("deployer_errors", "Deploy failed")
    error_signal = signal("deploy_failed", "Signals a failed deployment")
    success_counter = Counter("deployer_success", "Deploy successful")
    success_signal = signal("deploy_success", "Signals a successful deployment")
    deploy_histogram = Histogram("deployer_time_to_deploy", "Time spent on each deploy")

    def time(self, app_spec):
        self.deploy_counter.inc()
        self.deploy_signal.send(image=app_spec.image)
        return self.deploy_histogram.time()

    def failed(self, app_spec):
        self.error_counter.inc()
        self.error_signal.send(image=app_spec.image)

    def success(self, app_spec):
        self.success_counter.inc()
        self.success_signal.send(image=app_spec.image)


def _make_gen(func):
    while True:
        yield func()
