#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import pinject

from .watcher import Watcher


class ThirdPartyResourceBindings(pinject.BindingSpec):
    def configure(self, bind, require):
        require("config")
        require("deploy_queue")

        bind("tpr_watcher", to_class=Watcher)


class DisabledThirdPartyResourceBindings(pinject.BindingSpec):
    def configure(self, bind):
        bind("tpr_watcher", to_class=FakeWatcher)


class FakeWatcher(object):
    def start(self):
        pass

    def is_alive(self):
        return True
