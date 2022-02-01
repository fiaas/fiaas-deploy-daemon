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

import pinject

from .adapter import K8s
from .autoscaler import AutoscalerDeployer
from .deployment import DeploymentBindings
from .ingress import IngressDeployer, IngressTLSDeployer
from .ingress_v1beta1 import V1Beta1IngressAdapter
from .ingress_networkingv1 import NetworkingV1IngressAdapter
from .service import ServiceDeployer
from .service_account import ServiceAccountDeployer
from .owner_references import OwnerReferences
from k8s.models.ingress import IngressTLS as V1Beta1IngressTLS
from k8s.models.networking_v1_ingress import IngressTLS as StableIngressTLS


class K8sAdapterBindings(pinject.BindingSpec):
    def __init__(self, use_networkingv1_ingress):
        self.use_networkingv1_ingress = use_networkingv1_ingress

    def configure(self, bind):
        bind("adapter", to_class=K8s)
        bind("service_deployer", to_class=ServiceDeployer)
        bind("service_account_deployer", to_class=ServiceAccountDeployer)
        bind("ingress_deployer", to_class=IngressDeployer)
        bind("autoscaler", to_class=AutoscalerDeployer)
        bind("ingress_tls_deployer", to_class=IngressTLSDeployer)
        bind("owner_references", to_class=OwnerReferences)

        if self.use_networkingv1_ingress:
            bind("ingress_adapter", to_class=NetworkingV1IngressAdapter)
            bind("ingress_tls", to_instance=StableIngressTLS)
        else:
            bind("ingress_adapter", to_class=V1Beta1IngressAdapter)
            bind("ingress_tls", to_instance=V1Beta1IngressTLS)

    def dependencies(self):
        return [DeploymentBindings()]
