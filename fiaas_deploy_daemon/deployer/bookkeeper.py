#!/usr/bin/env python
# -*- coding: utf-8

from blinker import signal
from prometheus_client import Counter, Gauge, Histogram

DEPLOY_FAILED = "deploy_failed"
DEPLOY_STARTED = "deploy_started"
DEPLOY_SUCCESS = "deploy_success"


class Bookkeeper(object):
    """Measures time, fails and successes"""
    deploy_gauge = Gauge("deployer_requests", "Request to deploy an app", ["app"])
    deploy_signal = signal(DEPLOY_STARTED, "Signals start of deployment")
    error_counter = Counter("deployer_errors", "Deploy failed", ["app"])
    error_signal = signal(DEPLOY_FAILED, "Signals a failed deployment")
    success_counter = Counter("deployer_success", "Deploy successful", ["app"])
    success_signal = signal(DEPLOY_SUCCESS, "Signals a successful deployment")
    deploy_histogram = Histogram("deployer_time_to_deploy", "Time spent on each deploy")

    def time(self, app_spec):
        self.deploy_gauge.labels(app_spec.name).inc()
        self.deploy_signal.send(app_spec=app_spec)
        return self.deploy_histogram.time()

    def failed(self, app_name=None, namespace=None, deployment_id=None, app_spec=None):
        self.error_counter.labels(app_spec.name if app_spec else app_name).inc()
        self.error_signal.send(**{k: v for (k, v) in locals().items() if k not in ['self']})

    def success(self, app_spec):
        self.success_counter.labels(app_spec.name).inc()
        self.success_signal.send(app_spec=app_spec)
