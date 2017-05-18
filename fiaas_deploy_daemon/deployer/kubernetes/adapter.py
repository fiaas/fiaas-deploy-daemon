#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import logging
import time


LOG = logging.getLogger(__name__)


class K8s(object):
    """Adapt from an AppSpec to the necessary definitions for a kubernetes cluster
    """

    def __init__(self, config, service_deployer, deployment_deployer, ingress_deployer, autoscaler):
        self._version = config.version
        self._service_deployer = service_deployer
        self._deployment_deployer = deployment_deployer
        self._ingress_deployer = ingress_deployer
        self._autoscaler_deployer = autoscaler

    def deploy(self, app_spec):
        selector = _make_selector(app_spec)
        labels = self._make_labels(app_spec)
        self._service_deployer.deploy(app_spec, selector, labels)
        self._ingress_deployer.deploy(app_spec, labels)
        self._deployment_deployer.deploy(app_spec, selector, labels)
        self._autoscaler_deployer.deploy(app_spec, labels)

    def _make_labels(self, app_spec):
        labels = {
            "app": app_spec.name,
            "fiaas/version": app_spec.version,
            "fiaas/deployed_by": self._version,
            "fiaas/app_deployed_at": str(int(round(time.time()))),
        }

        _add_labels("fiaas/teams", labels, app_spec.teams)
        _add_labels("fiaas/tags", labels, app_spec.tags),
        return labels


# The value of labels can only be of the format (([A-Za-z0-9][-A-Za-z0-9_.]*)?[A-Za-z0-9])?
def _add_labels(prefix, labels, values):
    if values:
        counter = 0
        for value in values:
            post_fix = "_" + str(counter) if (counter > 0) else ""
            labels[prefix + post_fix] = _to_valid_label_value(value)
            counter = counter + 1


def _to_valid_label_value(value):
    return value.encode('utf-8').lower()\
        .replace(" ", "-").replace("ø", "oe").replace("å", "aa").replace("æ", "ae") \
        .replace(":", "-")


def _make_selector(app_spec):
    return {'app': app_spec.name}
