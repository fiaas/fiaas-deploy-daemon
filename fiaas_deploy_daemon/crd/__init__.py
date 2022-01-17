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

from .status import connect_signals
from .watcher import CrdWatcher
from .apiextensionsv1_crd_watcher import ApiextensionsV1CrdWatcher


class CustomResourceDefinitionBindings(pinject.BindingSpec):
    def __init__(self, use_apiextensionsv1_crd):
        self.use_apiextensionsv1_crd = use_apiextensionsv1_crd

    def configure(self, bind, require):
        require("config")
        require("deploy_queue")

        if self.use_apiextensionsv1_crd:
            bind("crd_watcher", to_class=ApiextensionsV1CrdWatcher)
        else:
            bind("crd_watcher", to_class=CrdWatcher)
        connect_signals()


class DisabledCustomResourceDefinitionBindings(pinject.BindingSpec):
    def configure(self, bind):
        bind("crd_watcher", to_class=FakeWatcher)


class FakeWatcher(object):
    def start(self):
        pass

    def is_alive(self):
        return True
