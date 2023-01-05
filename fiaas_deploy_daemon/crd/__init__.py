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


import pinject

from .crd_resources_syncer_apiextensionsv1 import CrdResourcesSyncerApiextensionsV1
from .crd_resources_syncer_apiextensionsv1beta1 import CrdResourcesSyncerApiextensionsV1Beta1

from .status import connect_signals
from .watcher import CrdWatcher


class CustomResourceDefinitionBindings(pinject.BindingSpec):
    def __init__(self, use_apiextensionsv1_crd):
        self.use_apiextensionsv1_crd = use_apiextensionsv1_crd

    def configure(self, bind, require):
        require("config")
        require("deploy_queue")

        bind("crd_watcher", to_class=CrdWatcher)
        if self.use_apiextensionsv1_crd:
            bind("crd_resources_syncer", to_class=CrdResourcesSyncerApiextensionsV1)
        else:
            bind("crd_resources_syncer", to_class=CrdResourcesSyncerApiextensionsV1Beta1)
        connect_signals()


class DisabledCustomResourceDefinitionBindings(pinject.BindingSpec):
    def configure(self, bind):
        bind("crd_watcher", to_class=FakeWatcher)


class FakeWatcher(object):
    def start(self):
        pass

    def is_alive(self):
        return True
