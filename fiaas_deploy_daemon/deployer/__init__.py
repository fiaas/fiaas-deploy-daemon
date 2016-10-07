#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import pinject

from .deploy import Deployer
from .bookkeeper import Bookkeeper
from .scheduler import Scheduler


class DeployerBindings(pinject.BindingSpec):
    def configure(self, bind, require):
        require("config")
        require("deploy_queue")
        require("adapter")
        bind("bookkeeper", to_class=Bookkeeper)
        bind("scheduler", to_class=Scheduler)
        bind("deployer", to_class=Deployer)
