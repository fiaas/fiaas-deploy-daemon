#!/usr/bin/env python
# -*- coding: utf-8

from blinker import signal
from prometheus_client import Counter, Gauge, Histogram


class Bookkeeper(object):
    """Measures time, fails and successes"""
    deploy_gauge = Gauge("deployer_requests", "Request to deploy an app", ["app"])
    deploy_signal = signal("deploy_started", "Signals start of deployment")
    error_counter = Counter("deployer_errors", "Deploy failed", ["app"])
    error_signal = signal("deploy_failed", "Signals a failed deployment")
    success_counter = Counter("deployer_success", "Deploy successful", ["app"])
    success_signal = signal("deploy_success", "Signals a successful deployment")
    deploy_histogram = Histogram("deployer_time_to_deploy", "Time spent on each deploy")

    def time(self, app_spec):
        self.deploy_gauge.labels(app_spec.name).inc()
        self.deploy_signal.send(app_spec=app_spec)
        return self.deploy_histogram.time()

    def failed(self, app_spec):
        self.error_counter.labels(app_spec.name).inc()
        self.error_signal.send(app_spec=app_spec)

    def success(self, app_spec):
        self.success_counter.labels(app_spec.name).inc()
        self.success_signal.send(app_spec=app_spec)
