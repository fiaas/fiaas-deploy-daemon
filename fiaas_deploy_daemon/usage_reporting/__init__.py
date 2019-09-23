#!/usr/bin/env python
# -*- coding: utf-8

# Copyright 2017-2019 The FIAAS Authors
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#      http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


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
        key = secrets.usage_reporting_key
        tenant = config.usage_reporting_tenant
        LOG.debug("Usage auth key is %s, tenant: %r", "set" if key else "not set", tenant)
        if key and tenant:
            LOG.debug("Usage auth enabled")
            return DevHoseAuth(key, tenant)
        LOG.debug("Usage auth disabled")
        return False
