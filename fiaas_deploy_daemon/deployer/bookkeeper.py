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
from prometheus_client import Counter, Gauge, Histogram

from fiaas_deploy_daemon.specs.models import AppSpec


class Bookkeeper(object):
    """Measures time, fails and successes"""

    deploy_gauge = Gauge("deployer_requests", "Request to deploy an app", ["app"])
    error_counter = Counter("deployer_errors", "Deploy failed", ["app"])
    success_counter = Counter("deployer_success", "Deploy successful", ["app"])
    deploy_histogram = Histogram("deployer_time_to_deploy", "Time spent on each deploy")

    def time(self, app_spec: AppSpec):
        self.deploy_gauge.labels(app_spec.name).inc()
        return self.deploy_histogram.time()

    def failed(self, app_spec: AppSpec):
        self.error_counter.labels(app_spec.name).inc()

    def success(self, app_spec: AppSpec):
        self.success_counter.labels(app_spec.name).inc()
