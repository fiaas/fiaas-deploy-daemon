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

from fiaas_deploy_daemon.config import Configuration
from fiaas_deploy_daemon.deployer import DeployerEvent
from fiaas_deploy_daemon.deployer.bookkeeper import Bookkeeper
from fiaas_deploy_daemon.deployer.deploy import Deployer
from fiaas_deploy_daemon.deployer.kubernetes.adapter import K8s
from fiaas_deploy_daemon.deployer.kubernetes.ready_check import ReadyCheck
from fiaas_deploy_daemon.deployer.scheduler import Scheduler
from fiaas_deploy_daemon.lifecycle import Lifecycle, Subject, STATUS_STARTED, STATUS_FAILED
from fiaas_deploy_daemon.specs.models import LabelAndAnnotationSpec


class TestDeploy(object):
    @pytest.fixture
    def bookkeeper(self):
        return mock.create_autospec(Bookkeeper)

    @pytest.fixture
    def lifecycle(self):
        lifecycle = Lifecycle()
        lifecycle.state_change_signal = mock.MagicMock()
        return lifecycle

    @pytest.fixture
    def adapter(self):
        return mock.create_autospec(K8s)

    @pytest.fixture
    def scheduler(self):
        return mock.create_autospec(Scheduler)

    @pytest.fixture
    def lifecycle_subject(self, app_spec):
        return Subject(app_spec.name, app_spec.namespace, app_spec.deployment_id, None,
                       app_spec.labels.status, app_spec.annotations.status)

    @pytest.fixture
    def config(self):
        return Configuration([])

    @pytest.fixture
    def deployer(self, app_spec, bookkeeper, adapter, scheduler, lifecycle, lifecycle_subject, config):
        deployer = Deployer(Queue(), bookkeeper, adapter, scheduler, lifecycle, config)
        deployer._queue = [DeployerEvent("UPDATE", app_spec, lifecycle_subject)]
        return deployer

    def test_use_adapter_to_deploy(self, app_spec, deployer, adapter):
        deployer()

        adapter.deploy.assert_called_with(app_spec)

    @pytest.mark.parametrize("annotations,repository", [
        (None, None),
        ({"fiaas/source-repository": "xyz"}, "xyz"),
    ])
    def test_signals_start_of_deploy(self, app_spec, lifecycle, lifecycle_subject, deployer, annotations, repository):
        if annotations:
            app_spec = app_spec._replace(annotations=LabelAndAnnotationSpec(*[annotations] * 6))
        deployer._queue = [DeployerEvent("UPDATE", app_spec, lifecycle_subject)]
        deployer()

        lifecycle.state_change_signal.send.assert_called_with(status=STATUS_STARTED, subject=lifecycle_subject)

    @pytest.mark.parametrize("annotations,repository", [
        (None, None),
        ({"fiaas/source-repository": "xyz"}, "xyz"),
    ])
    def test_signals_failure_on_exception(self, app_spec, lifecycle, lifecycle_subject, deployer, adapter, annotations, repository):
        if annotations:
            app_spec = app_spec._replace(annotations=LabelAndAnnotationSpec(*[annotations] * 6))
        deployer._queue = [DeployerEvent("UPDATE", app_spec, lifecycle_subject)]
        adapter.deploy.side_effect = Exception("message")

        deployer()

        lifecycle.state_change_signal.send.assert_called_with(status=STATUS_FAILED, subject=lifecycle_subject)

    def test_schedules_ready_check(self, app_spec, scheduler, bookkeeper, deployer, lifecycle, lifecycle_subject,
                                   config):
        deployer()

        lifecycle.state_change_signal.send.assert_called_once_with(status=STATUS_STARTED, subject=lifecycle_subject)
        scheduler.add.assert_called_with(ReadyCheck(app_spec, bookkeeper, lifecycle, lifecycle_subject, config))
