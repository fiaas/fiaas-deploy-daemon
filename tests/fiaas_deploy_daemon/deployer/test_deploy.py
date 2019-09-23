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


from Queue import Queue

import mock
import pytest
from fiaas_deploy_daemon.deployer.bookkeeper import Bookkeeper
from fiaas_deploy_daemon.deployer.deploy import Deployer
from fiaas_deploy_daemon.deployer import DeployerEvent
from fiaas_deploy_daemon.deployer.scheduler import Scheduler
from fiaas_deploy_daemon.deployer.kubernetes.adapter import K8s
from fiaas_deploy_daemon.deployer.kubernetes.ready_check import ReadyCheck
from fiaas_deploy_daemon.lifecycle import Lifecycle
from fiaas_deploy_daemon.specs.models import LabelAndAnnotationSpec


class TestDeploy(object):
    @pytest.fixture
    def bookkeeper(self):
        return mock.create_autospec(Bookkeeper)

    @pytest.fixture
    def lifecycle(self):
        lifecycle = Lifecycle()
        lifecycle.deploy_signal = mock.MagicMock()
        lifecycle.success_signal = mock.MagicMock()
        lifecycle.error_signal = mock.MagicMock()
        return lifecycle

    @pytest.fixture
    def adapter(self):
        return mock.create_autospec(K8s)

    @pytest.fixture
    def scheduler(self):
        return mock.create_autospec(Scheduler)

    @pytest.fixture
    def deployer(self, app_spec, bookkeeper, adapter, scheduler, lifecycle):
        deployer = Deployer(Queue(), bookkeeper, adapter, scheduler, lifecycle)
        deployer._queue = [DeployerEvent("UPDATE", app_spec)]
        return deployer

    def test_use_adapter_to_deploy(self, app_spec, deployer, adapter):
        deployer()

        adapter.deploy.assert_called_with(app_spec)

    @pytest.mark.parametrize("annotations,repository", [
        (None, None),
        ({"fiaas/source-repository": "xyz"}, "xyz"),
    ])
    def test_signals_start_of_deploy(self, app_spec, lifecycle, deployer, annotations, repository):
        if annotations:
            app_spec = app_spec._replace(annotations=LabelAndAnnotationSpec(*[annotations] * 5))
        deployer._queue = [DeployerEvent("UPDATE", app_spec)]
        deployer()

        lifecycle.deploy_signal.send.assert_called_with(app_name=app_spec.name, namespace=app_spec.namespace,
                                                        deployment_id=app_spec.deployment_id, repository=repository)

    @pytest.mark.parametrize("annotations,repository", [
        (None, None),
        ({"fiaas/source-repository": "xyz"}, "xyz"),
    ])
    def test_signals_failure_on_exception(self, app_spec, lifecycle, deployer, adapter, annotations, repository):
        if annotations:
            app_spec = app_spec._replace(annotations=LabelAndAnnotationSpec(*[annotations] * 5))
        deployer._queue = [DeployerEvent("UPDATE", app_spec)]
        adapter.deploy.side_effect = Exception("message")

        deployer()

        lifecycle.success_signal.send.assert_not_called()
        lifecycle.error_signal.send.assert_called_with(app_name=app_spec.name, namespace=app_spec.namespace,
                                                       deployment_id=app_spec.deployment_id, repository=repository)

    def test_schedules_ready_check(self, app_spec, scheduler, bookkeeper, deployer, lifecycle):
        deployer()

        lifecycle.error_signal.send.assert_not_called()
        scheduler.add.assert_called_with(ReadyCheck(app_spec, bookkeeper, lifecycle))
