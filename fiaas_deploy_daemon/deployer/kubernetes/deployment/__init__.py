#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import pinject as pinject

from .datadog import DataDog
from .deployer import DeploymentDeployer


class DeploymentBindings(pinject.BindingSpec):
    def configure(self, bind):
        bind("datadog", to_class=DataDog)
        bind("deployment_deployer", to_class=DeploymentDeployer)
