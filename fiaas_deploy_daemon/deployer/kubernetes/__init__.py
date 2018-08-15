#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import pinject

from .adapter import K8s
from .autoscaler import AutoscalerDeployer
from .deployment import DeploymentBindings
from .ingress import IngressDeployer
from .service import ServiceDeployer


class K8sAdapterBindings(pinject.BindingSpec):
    def configure(self, bind):
        bind("adapter", to_class=K8s)
        bind("service_deployer", to_class=ServiceDeployer)
        bind("ingress_deployer", to_class=IngressDeployer)
        bind("autoscaler", to_class=AutoscalerDeployer)

    def dependencies(self):
        return [DeploymentBindings()]
