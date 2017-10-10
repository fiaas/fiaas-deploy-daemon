#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import importlib
import pkgutil

import pinject

from .app_config_downloader import AppConfigDownloader
from .factory import SpecFactory


class SpecBindings(pinject.BindingSpec):
    def configure(self, bind):
        bind("spec_factory", to_class=SpecFactory)
        bind("app_config_downloader", to_class=AppConfigDownloader)

    def provide_factory(self):
        from .v2 import Factory
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
