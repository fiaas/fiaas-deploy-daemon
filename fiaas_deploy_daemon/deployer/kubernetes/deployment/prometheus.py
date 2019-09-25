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

from fiaas_deploy_daemon.tools import merge_dicts

LOG = logging.getLogger(__name__)


class Prometheus(object):
    def apply(self, deployment, app_spec):
        if app_spec.prometheus.enabled:
            annotations = _make_prometheus_annotations(app_spec)
            original_annotations = deployment.spec.template.metadata.annotations
            deployment.spec.template.metadata.annotations = merge_dicts(original_annotations, annotations)


def _make_prometheus_annotations(app_spec):
    lookup = {p.name: p.target_port for p in app_spec.ports}
    prometheus_spec = app_spec.prometheus
    try:
        port = int(prometheus_spec.port)
    except ValueError:
        try:
            port = lookup[prometheus_spec.port]
        except KeyError:
            LOG.error("Invalid prometheus configuration for %s", app_spec.name)
            return {}
    return {
        "prometheus.io/scrape": str(prometheus_spec.enabled).lower(),
        "prometheus.io/port": str(port),
        "prometheus.io/path": prometheus_spec.path
    }
