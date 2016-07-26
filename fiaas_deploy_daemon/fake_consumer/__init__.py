#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import
import pinject
from .fake_consumer import FakeConsumer


class FakeConsumerBindings(pinject.BindingSpec):
    def configure(self, bind):
        bind("consumer", to_class=FakeConsumer)
