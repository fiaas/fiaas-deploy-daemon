#!/usr/bin/env python
# -*- coding: utf-8

from blinker import signal
from prometheus_client import Counter, Histogram


class Bookkeeper(object):
    """Trigger signals and counters"""
    deploy_counter = Counter("deployer_requests", "Request to deploy an app", ["app"])
    deploy_signal = signal("deploy_started", "Signals start of deployment")
    error_counter = Counter("deployer_errors", "Deploy failed", ["app"])
    error_signal = signal("deploy_failed", "Signals a failed deployment")
    success_counter = Counter("deployer_success", "Deploy successful", ["app"])
    success_signal = signal("deploy_success", "Signals a successful deployment")
    deploy_histogram = Histogram("deployer_time_to_deploy", "Time spent on each deploy")

    def time(self, app_spec):
        self.deploy_counter.labels(app_spec.name).inc()
        self.deploy_signal.send(image=app_spec.image)
        return self.deploy_histogram.time()

    def failed(self, app_spec):
        self.error_counter.labels(app_spec.name).inc()
        self.error_signal.send(image=app_spec.image)

    def success(self, app_spec):
        self.success_counter.labels(app_spec.name).inc()
        self.success_signal.send(image=app_spec.image)
