#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import pinject

from .factory import SpecFactory


class SpecBindings(pinject.BindingSpec):
    def configure(self, bind):
        bind("spec_factory", to_class=SpecFactory)


class InvalidConfiguration(Exception):
    pass
