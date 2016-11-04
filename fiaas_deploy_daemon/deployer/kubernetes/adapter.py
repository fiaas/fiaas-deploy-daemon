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

        _add_teams_label(labels, app_spec.teams)
        _add_tag_label(labels, app_spec.tags),
        return labels


def _add_teams_label(labels, value):
    if value:
        labels["fiaas/teams"] = _to_valid_label_value(value)


# The value of labels can only be of the format (([A-Za-z0-9][-A-Za-z0-9_.]*)?[A-Za-z0-9])?
def _add_tag_label(labels, values):
    if values:
        counter = 0
        for value in values.split(" "):
            post_fix = "_" + str(counter) if (counter > 0) else ""
            labels["fiaas/tags" + post_fix] = _to_valid_label_value(value)
            counter = counter + 1


def _to_valid_label_value(value):
    return str(value).lower().replace(" ", "-").replace("ø", "oe").replace("å", "aa").replace("æ", "ae")


def _make_selector(app_spec):
    return {
        'app': app_spec.name,
    }
