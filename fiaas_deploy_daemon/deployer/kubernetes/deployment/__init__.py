#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import pinject as pinject

from .datadog import DataDog
from .deployer import DeploymentDeployer
from .prometheus import Prometheus
from .secrets import Secrets


class DeploymentBindings(pinject.BindingSpec):
    def configure(self, bind):
        bind("datadog", to_class=DataDog)
        bind("prometheus", to_class=Prometheus)
        bind("secrets", to_class=Secrets)
        bind("deployment_deployer", to_class=DeploymentDeployer)
