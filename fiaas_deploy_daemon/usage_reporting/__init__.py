#!/usr/bin/env python
# -*- coding: utf-8

import logging

import pinject

from .dev_hose_auth import DevHoseAuth
from .transformer import DevhoseDeploymentEventTransformer
from .usage_reporter import UsageReporter

LOG = logging.getLogger(__name__)


class UsageReportingBindings(pinject.BindingSpec):
    def configure(self, bind, require):
        require("config")
        require("session")
        require("secrets")
        bind("usage_transformer", to_class=DevhoseDeploymentEventTransformer)
        bind("usage_reporter", to_class=UsageReporter)

    def provide_usage_auth(self, config, secrets):
        key = secrets.tracking_key
        tenant = config.tracking_tenant
        LOG.debug("Usage auth key is %s, tenant: %r", "set" if key else "not set", tenant)
        if key and tenant:
            LOG.debug("Usage auth enabled")
            return DevHoseAuth(key, tenant)
        LOG.debug("Usage auth disabled")
        return False
