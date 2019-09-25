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
from __future__ import unicode_literals, absolute_import

import mock
import pytest
from blinker import signal
from requests.auth import AuthBase

from fiaas_deploy_daemon import Configuration
from fiaas_deploy_daemon.lifecycle import DEPLOY_FAILED, DEPLOY_STARTED, DEPLOY_SUCCESS
from fiaas_deploy_daemon.usage_reporting import DevhoseDeploymentEventTransformer
from fiaas_deploy_daemon.usage_reporting.usage_reporter import UsageReporter, UsageEvent


class TestUsageReporter(object):
    @pytest.fixture
    def config(self):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.usage_reporting_endpoint = "http://example.com/usage"
        return config

    @pytest.fixture
    def mock_transformer(self, config):
        return mock.create_autospec(DevhoseDeploymentEventTransformer(config))

    @pytest.fixture
    def mock_session(self):
        return mock.NonCallableMagicMock()

    @pytest.fixture
    def mock_auth(self):
        return mock.create_autospec(AuthBase())

    @pytest.mark.parametrize("signal_name,repository", [
        (DEPLOY_STARTED, None),
        (DEPLOY_FAILED, None),
        (DEPLOY_SUCCESS, None),
        (DEPLOY_STARTED, "repo"),
        (DEPLOY_FAILED, "repo"),
        (DEPLOY_SUCCESS, "repo"),
    ])
    def test_signal_to_event(self, config, mock_transformer, mock_session, mock_auth, app_spec, signal_name, repository):
        reporter = UsageReporter(config, mock_transformer, mock_session, mock_auth)

        signal(signal_name).send(app_name=app_spec.name, namespace=app_spec.namespace, deployment_id=app_spec.deployment_id,
                                 repository=repository)

        event = reporter._event_queue.get_nowait()

        assert event.status == signal_name.split("_")[-1].upper()
        assert event.app_name == app_spec.name
        assert event.namespace == app_spec.namespace
        assert event.deployment_id == app_spec.deployment_id
        assert event.repository == repository

    def test_event_to_transformer(self, config, mock_transformer, mock_session, mock_auth):
        event = UsageEvent("status", "name", "namespace", "deployment_id", "repository")
        reporter = UsageReporter(config, mock_transformer, mock_session, mock_auth)
        reporter._event_queue = [event]

        reporter()

        mock_transformer.assert_called_once_with(event.status, event.app_name, event.namespace, event.deployment_id,
                                                 event.repository)

    def test_post_to_webhook(self, config, mock_transformer, mock_session, mock_auth):
        event = UsageEvent("status", "name", "namespace", "deployment_id", "repository")
        reporter = UsageReporter(config, mock_transformer, mock_session, mock_auth)
        reporter._event_queue = [event]

        payload = {"dummy": "payload"}
        mock_transformer.return_value = payload

        reporter()

        mock_session.post.assert_called_once_with(config.usage_reporting_endpoint, json=payload, auth=mock_auth)
