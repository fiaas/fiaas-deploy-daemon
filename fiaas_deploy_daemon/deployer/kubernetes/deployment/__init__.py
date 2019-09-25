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
from __future__ import absolute_import

import pinject as pinject

from .datadog import DataDog
from .deployer import DeploymentDeployer
from .prometheus import Prometheus
from .secrets import Secrets, KubernetesSecrets, GenericInitSecrets, StrongboxSecrets


class DeploymentBindings(pinject.BindingSpec):
    def configure(self, bind):
        bind("datadog", to_class=DataDog)
        bind("prometheus", to_class=Prometheus)
        bind("kubernetes_secrets", to_class=KubernetesSecrets)
        bind("generic_init_secrets", to_class=GenericInitSecrets)
        bind("strongbox_secrets", to_class=StrongboxSecrets)
        bind("deployment_secrets", to_class=Secrets)
        bind("deployment_deployer", to_class=DeploymentDeployer)
