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


# In version 0.20, the none-driver is supposed to work, but in general it segfaults
# and does weird things as root, so it doesn't look like it's ready yet.
class NoneDriver(LinuxDriver):
    name = "none"
    arguments = ("--vm-driver", "none", "--use-vendored-driver")

    def supported(self, minikube_version):
        if minikube_version < StrictVersion("0.20"):
            return has_utility("systemctl") and has_utility("docker")
        return has_utility("docker")
