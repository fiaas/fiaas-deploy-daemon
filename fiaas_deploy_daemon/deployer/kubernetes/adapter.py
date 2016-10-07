#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import logging

from k8s import config as k8s_config

from .service import deploy_service

LOG = logging.getLogger(__name__)


class K8s(object):
    """Adapt from an AppSpec to the necessary definitions for a kubernetes cluster
    """

    def __init__(self, config, deployment_deployer, ingress_deployer):
        k8s_config.api_server = config.api_server
        k8s_config.api_token = config.api_token
        if config.api_cert:
            k8s_config.verify_ssl = config.api_cert
        else:
            k8s_config.verify_ssl = not config.debug
        if config.client_cert:
            k8s_config.cert = (config.client_cert, config.client_key)
        k8s_config.debug = config.debug
        self._version = config.version
        self._deployment_deployer = deployment_deployer
        self._ingress_deployer = ingress_deployer

    def deploy(self, app_spec):
        selector = _make_selector(app_spec)
        labels = self._make_labels(app_spec)
        deploy_service(app_spec, selector, labels)
        self._ingress_deployer.deploy(app_spec, labels)
        self._deployment_deployer.deploy(app_spec, selector, labels)

    def _make_labels(self, app_spec):
        labels = {
            "app": app_spec.name,
            "fiaas/version": app_spec.version,
            "fiaas/deployed_by": self._version,
        }
        return labels


def _make_selector(app_spec):
    return {'app': app_spec.name}
