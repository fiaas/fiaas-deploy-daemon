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
import os


def has_utility(cmd):
    path = os.environ['PATH']
    return any(os.access(os.path.join(p, cmd), os.X_OK) for p in path.split(os.pathsep))


def is_macos():
    return os.uname()[0] == 'Darwin'


class Driver(object):
    arch = "amd64"

    @property
    def name(self):
        raise NotImplementedError("Subclass must set name")

    @property
    def arguments(self):
        return "--vm-driver", self.name


class LinuxDriver(Driver):
    os = "linux"


class MacDriver(Driver):
    os = "darwin"
