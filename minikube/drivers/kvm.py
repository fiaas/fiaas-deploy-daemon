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
from distutils.version import StrictVersion

from .common import has_utility, LinuxDriver


class KVMDriver(LinuxDriver):
    name = "kvm"

    def supported(self, minikube_version):
        if minikube_version < StrictVersion("0.5"):
            return False
        return has_utility("docker-machine-driver-kvm")


class KVM2Driver(LinuxDriver):
    name = "kvm2"

    def supported(self, minikube_version):
        return has_utility("docker-machine-driver-kvm2")
