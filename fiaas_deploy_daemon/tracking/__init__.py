#!/usr/bin/env python
# -*- coding: utf-8

import logging

import pinject

from .dev_hose_auth import DevHoseAuth
from .transformer import DevhoseDeploymentEventTransformer
from .usage_reporter import UsageReporter

LOG = logging.getLogger(__name__)


class TrackingBindings(pinject.BindingSpec):
    def configure(self, bind, require):
        require("config")
        require("session")
        require("secrets")
        bind("usage_transformer", to_class=DevhoseDeploymentEventTransformer)
        bind("usage_reporter", to_class=UsageReporter)

    def provide_usage_auth(self, config, secrets):
        key = secrets.tracking_key
        tenant = config.tracking_tenant
        if key and tenant:
            return DevHoseAuth(key, tenant)
        LOG.debug("Usage auth disabled. Key is %s, Tenant: %r", "set" if key else "not set", tenant)
        return False
