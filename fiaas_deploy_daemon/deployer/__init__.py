#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import pinject

from .deploy import Deployer
from .kubernetes import K8s


class DeployerBindings(pinject.BindingSpec):
    def configure(self, bind, require):
        require("config")
        require("deploy_queue")
        bind("adapter", to_class=K8s)
        bind("deployer", to_class=Deployer)
