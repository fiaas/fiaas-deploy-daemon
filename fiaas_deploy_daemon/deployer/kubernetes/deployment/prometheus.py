#!/usr/bin/env python
# -*- coding: utf-8
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
