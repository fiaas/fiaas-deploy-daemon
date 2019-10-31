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

import pytest
from blinker import signal
from mock import create_autospec
from requests import Session

from fiaas_deploy_daemon.config import Configuration
from fiaas_deploy_daemon.lifecycle import DEPLOY_FAILED, DEPLOY_STARTED, DEPLOY_SUCCESS
from fiaas_deploy_daemon.pipeline.reporter import Reporter

CALLBACK = u"http://example.com/callback/"
DEPLOYMENT_ID = u"deployment_id"
NAME = u"testapp"


class TestReporter(object):
    @pytest.fixture
    def session(self):
        return create_autospec(Session, spec_set=True)

    @pytest.fixture
    def config(self):
        mock_config = create_autospec(Configuration([]), spec_set=True)
        mock_config.infrastructure = u"diy"
        mock_config.environment = u"test"
        return mock_config

    @pytest.mark.parametrize("signal_name,url", [
        (DEPLOY_STARTED, u"fiaas_test-diy_deploy_started/success"),
        (DEPLOY_FAILED, u"fiaas_test-diy_deploy_end/failure"),
        (DEPLOY_SUCCESS, u"fiaas_test-diy_deploy_end/success")
    ])
    def test_signal_to_callback(self, session, config, signal_name, url, app_spec):
        reporter = Reporter(config, session)
        reporter.register(app_spec, CALLBACK)

        signal(signal_name).send(app_name=app_spec.name,
                                 namespace=app_spec.namespace,
                                 deployment_id=app_spec.deployment_id)

        session.post.assert_called_with(CALLBACK + url,
                                        json={u"description": u"From fiaas-deploy-daemon"})
