#!/usr/bin/env python
# -*- coding: utf-8

from Queue import Queue

import mock
import pytest
from fiaas_deploy_daemon.deployer.bookkeeper import Bookkeeper
from fiaas_deploy_daemon.deployer.deploy import Deployer
from fiaas_deploy_daemon.deployer import DeployerEvent
from fiaas_deploy_daemon.deployer.scheduler import Scheduler
from fiaas_deploy_daemon.deployer.kubernetes.adapter import K8s
from fiaas_deploy_daemon.deployer.kubernetes.ready_check import ReadyCheck


class TestDeploy(object):
    @pytest.fixture
    def bookkeeper(self):
        bookkeeper = Bookkeeper()
        bookkeeper.deploy_signal = mock.MagicMock()
        bookkeeper.success_signal = mock.MagicMock()
        bookkeeper.error_signal = mock.MagicMock()
        return bookkeeper

    @pytest.fixture
    def adapter(self):
        return mock.create_autospec(K8s)

    @pytest.fixture
    def scheduler(self):
        return mock.create_autospec(Scheduler)

    @pytest.fixture
    def deployer(self, app_spec, bookkeeper, adapter, scheduler):
        deployer = Deployer(Queue(), bookkeeper, adapter, scheduler)
        deployer._queue = [DeployerEvent("UPDATE", app_spec)]
        return deployer

    def test_use_adapter_to_deploy(self, app_spec, deployer, adapter):
        deployer()

        adapter.deploy.assert_called_with(app_spec)

    def test_signals_start_of_deploy(self, app_spec, bookkeeper, deployer):
        deployer()

        bookkeeper.deploy_signal.send.assert_called_with(app_spec=app_spec)

    def test_signals_failure_on_exception(self, app_spec, bookkeeper, deployer, adapter):
        adapter.deploy.side_effect = Exception("message")

        deployer()

        bookkeeper.success_signal.send.assert_not_called()
        bookkeeper.error_signal.send.assert_called_with(app_spec=app_spec)

    def test_schedules_ready_check(self, app_spec, scheduler, bookkeeper, deployer):
        deployer()

        bookkeeper.error_signal.send.assert_not_called()
        scheduler.add.assert_called_with(ReadyCheck(app_spec, bookkeeper))
