#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import pinject

from .usage_reporter import UsageReporter


class UsageBindings(pinject.BindingSpec):
    def configure(self, bind, require):
        require("session")
        require("config")
        bind("usage_auth", to_class=Dummy)
        bind("usage_transformer", to_class=Dummy)
        bind("usage_reporter", to_class=UsageReporter)


class Dummy(object):
    def __call__(self, *args, **kwargs):
        pass

    def transform(self, *args):
        pass
