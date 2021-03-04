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

import importlib
import pkgutil

import pinject

from .default import DefaultAppSpec
from .factory import SpecFactory


class SpecBindings(pinject.BindingSpec):
    def configure(self, bind):
        bind("spec_factory", to_class=SpecFactory)
        bind("default_app_spec", to_class=DefaultAppSpec)

    def provide_factory(self):
        from .v3 import Factory
        return Factory()

    def provide_transformers(self):
        transformers = {}
        for _, name, ispkg in pkgutil.iter_modules(__path__):
            if ispkg and name.startswith("v"):
                version = int(name[1])
                module = importlib.import_module("{}.{}".format(__name__, name))
                try:
                    transformers[version] = module.Transformer()
                except AttributeError:
                    pass
        return transformers
