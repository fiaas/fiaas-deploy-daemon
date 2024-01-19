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

from k8s.models.resourcequota import ResourceQuota, NotBestEffort

from ...specs.models import AppSpec, ResourcesSpec, ResourceRequirementSpec

from .autoscaler import AutoscalerDeployer
from .deployment import DeploymentDeployer
from .ingress import IngressDeployer
from .service import ServiceDeployer
from .service_account import ServiceAccountDeployer
from .pod_disruption_budget import PodDisruptionBudgetDeployer

LOG = logging.getLogger(__name__)


class K8s(object):
    """Adapt from an AppSpec to the necessary definitions for a kubernetes cluster"""

    def __init__(
        self, config, service_deployer, deployment_deployer, ingress_deployer, autoscaler, service_account_deployer, pod_disruption_budget_deployer
    ):
        self._version = config.version
        self._enable_service_account_per_app = config.enable_service_account_per_app
        self._service_deployer: ServiceDeployer = service_deployer
        self._deployment_deployer: DeploymentDeployer = deployment_deployer
        self._ingress_deployer: IngressDeployer = ingress_deployer
        self._autoscaler_deployer: AutoscalerDeployer = autoscaler
        self._service_account_deployer: ServiceAccountDeployer = service_account_deployer
        self._pod_disruption_budget_deployer: PodDisruptionBudgetDeployer = pod_disruption_budget_deployer

    def deploy(self, app_spec: AppSpec):
        if _besteffort_qos_is_required(app_spec):
            app_spec = _remove_resource_requirements(app_spec)
        selector = _make_selector(app_spec)
        labels = self._make_labels(app_spec)
        if self._enable_service_account_per_app is True:
            self._service_account_deployer.deploy(app_spec, labels)
        self._service_deployer.deploy(app_spec, selector, labels)
        self._ingress_deployer.deploy(app_spec, labels)
        self._deployment_deployer.deploy(app_spec, selector, labels, _besteffort_qos_is_required(app_spec))
        self._autoscaler_deployer.deploy(app_spec, labels)
        self._pod_disruption_budget_deployer.deploy(app_spec, selector, labels)

    def delete(self, app_spec: AppSpec):
        self._ingress_deployer.delete(app_spec)
        self._autoscaler_deployer.delete(app_spec)
        self._service_deployer.delete(app_spec)
        self._deployment_deployer.delete(app_spec)
        self._pod_disruption_budget_deployer.delete(app_spec)

    def _make_labels(self, app_spec: AppSpec):
        labels = {
            "app": app_spec.name,
            "fiaas/version": app_spec.version,
            "fiaas/deployment_id": app_spec.deployment_id,
            "fiaas/deployed_by": self._version,
        }

        _add_labels("teams.fiaas", labels, app_spec.teams)
        _add_labels("tags.fiaas", labels, app_spec.tags),
        return labels


# The value of labels can only be of the format (([A-Za-z0-9][-A-Za-z0-9_.]*)?[A-Za-z0-9])?
def _add_labels(prefix, labels, values):
    for value in values:
        label = "{}/{}".format(prefix, _to_valid_label_value(value))
        labels[label] = "true"


def _to_valid_label_value(value):
    return value.lower().replace(" ", "-").replace("ø", "oe").replace("å", "aa").replace("æ", "ae").replace(":", "-")


def _make_selector(app_spec: AppSpec):
    return {"app": app_spec.name}


def _remove_resource_requirements(app_spec: AppSpec):
    no_requirements = ResourceRequirementSpec(cpu=None, memory=None)
    return app_spec._replace(resources=ResourcesSpec(limits=no_requirements, requests=no_requirements))


def _besteffort_qos_is_required(app_spec: AppSpec):
    resourcequotas = ResourceQuota.list(namespace=app_spec.namespace)
    return any(rq.spec.hard.get("pods") == "0" and NotBestEffort in rq.spec.scopes for rq in resourcequotas)
