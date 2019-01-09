#!/usr/bin/env python
# -*- coding: utf-8

from prometheus_client import Counter, Gauge, Histogram


class Bookkeeper(object):
    """Measures time, fails and successes"""
    deploy_gauge = Gauge("deployer_requests", "Request to deploy an app", ["app"])
    error_counter = Counter("deployer_errors", "Deploy failed", ["app"])
    success_counter = Counter("deployer_success", "Deploy successful", ["app"])
    deploy_histogram = Histogram("deployer_time_to_deploy", "Time spent on each deploy")

    def time(self, app_spec):
        self.deploy_gauge.labels(app_spec.name).inc()
        return self.deploy_histogram.time()

    def failed(self, app_spec):
        self.error_counter.labels(app_spec.name).inc()

    def success(self, app_spec):
        self.success_counter.labels(app_spec.name).inc()
