#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import pinject

from .usage_reporter import UsageReporter


class UsageBindings(pinject.BindingSpec):
    def configure(self, bind, require):
        require("session")
        bind("usage_reporter", to_class=UsageReporter)
