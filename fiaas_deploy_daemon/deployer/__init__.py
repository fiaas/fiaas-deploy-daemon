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


from collections import namedtuple

import pinject

from .bookkeeper import Bookkeeper
from .deploy import Deployer
from .scheduler import Scheduler


class DeployerBindings(pinject.BindingSpec):
    def configure(self, bind, require):
        require("config")
        require("deploy_queue")
        require("adapter")
        bind("bookkeeper", to_class=Bookkeeper)
        bind("scheduler", to_class=Scheduler)
        bind("deployer", to_class=Deployer)


DeployerEvent = namedtuple('DeployerEvent', ['action', 'app_spec', 'lifecycle_subject'])
