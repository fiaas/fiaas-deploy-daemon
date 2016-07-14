#!/usr/bin/env python
# -*- coding: utf-8

import pytest
from blinker import signal
from mock import create_autospec
from requests import Session

from fiaas_deploy_daemon.pipeline.reporter import Reporter

CALLBACK = u"http://example.com/callback/"
IMAGE = u"image"


class TestReporter(object):
    @pytest.fixture()
    def mock_session(self):
        mock_session = create_autospec(Session)
        return mock_session

    @pytest.mark.parametrize("signal_name,url", [
        ("deploy_started", u"fiaas_test_deploy_started/success"),
        ("deploy_failed", u"fiaas_test_deploy_end/failure"),
        ("deploy_success", u"fiaas_test_deploy_end/success")
    ])
    def test_signal_to_callback(self, mock_session, signal_name, url):
        reporter = Reporter(u"test", mock_session)
        reporter.register(IMAGE, CALLBACK)

        signal(signal_name).send(image=IMAGE)

        mock_session.post.assert_called_with(CALLBACK + url,
                                             json={u"description": u"From fiaas-deploy-daemon"})
