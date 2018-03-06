#!/usr/bin/env python
# -*- coding: utf-8

import pytest
from blinker import signal
from fiaas_deploy_daemon.config import Configuration
from fiaas_deploy_daemon.pipeline.reporter import Reporter
from fiaas_deploy_daemon.deployer.bookkeeper import DEPLOY_FAILED, DEPLOY_STARTED, DEPLOY_SUCCESS
from mock import create_autospec
from requests import Session

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

        signal(signal_name).send(app_spec=app_spec)

        session.post.assert_called_with(CALLBACK + url,
                                        json={u"description": u"From fiaas-deploy-daemon"})
