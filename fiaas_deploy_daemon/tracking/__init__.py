#!/usr/bin/env python
# -*- coding: utf-8
import pinject

from .transformer import DevhoseDeploymentEventTransformer


class TrackingBindings(pinject.BindingSpec):
    def configure(self, bind, require):
        require("config")
        bind("devhose_transformer", to_class=DevhoseDeploymentEventTransformer)
