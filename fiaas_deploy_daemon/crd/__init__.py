#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import pinject

from .watcher import CrdWatcher
from .status import connect_signals


class CustomResourceDefinitionBindings(pinject.BindingSpec):
    def configure(self, bind, require):
        require("config")
        require("deploy_queue")

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
