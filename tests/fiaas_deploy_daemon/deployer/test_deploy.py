#!/usr/bin/env python
# -*- coding: utf-8

from Queue import Queue

import mock

from fiaas_deploy_daemon.deployer.deploy import Deployer
from fiaas_deploy_daemon.deployer.kubernetes import K8s
from fiaas_deploy_daemon.specs.models import AppSpec

APP_SPEC = AppSpec(None, u"name", u"image", None, None, None, None, None, None)


class TestDeploy(object):
    def setup(self):
        self.mock_adapter = mock.create_autospec(K8s)
        self.deploy = Deployer(Queue(), self.mock_adapter)
        self.deploy._queue = [APP_SPEC]

    def test_use_adapter_to_deploy(self):
        self.deploy()

        self.mock_adapter.deploy.assert_called_with(APP_SPEC)

    @mock.patch("fiaas_deploy_daemon.deployer.deploy._Bookkeeper.deploy_signal")
    def test_signals_start_of_deploy(self, deploy_signal):
        self.deploy()

        deploy_signal.send.assert_called_with(image=APP_SPEC.image)

    @mock.patch("fiaas_deploy_daemon.deployer.deploy._Bookkeeper.success_signal")
    def test_signals_success(self, success_signal):
        self.deploy()

        success_signal.send.assert_called_with(image=APP_SPEC.image)

    @mock.patch("fiaas_deploy_daemon.deployer.deploy._Bookkeeper.error_signal")
    def test_signals_failure(self, error_signal):
        self.mock_adapter.deploy.side_effect = Exception("message")

        self.deploy()

        error_signal.send.assert_called_with(image=APP_SPEC.image)
