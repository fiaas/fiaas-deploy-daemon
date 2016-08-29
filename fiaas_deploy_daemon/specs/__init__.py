#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import importlib
import pkgutil

import pinject

from .factory import SpecFactory


class SpecBindings(pinject.BindingSpec):
    def configure(self, bind):
        bind("spec_factory", to_class=SpecFactory)

    def provide_factories(self):
        factories = {}
        for _, name, ispkg in pkgutil.iter_modules(__path__):
            if ispkg and name.startswith("v"):
                version = int(name[1])
                module = importlib.import_module("{}.{}".format(__name__, name))
                factories[version] = module.Factory()
        return factories


class InvalidConfiguration(Exception):
    pass
