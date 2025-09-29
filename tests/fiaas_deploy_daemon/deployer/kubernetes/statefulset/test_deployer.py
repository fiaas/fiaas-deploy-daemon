#!/usr/bin/env python
# -*- coding: utf-8

# Copyright 2017-2024 The FIAAS Authors
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

from unittest import mock

import pytest

from fiaas_deploy_daemon.config import Configuration
from fiaas_deploy_daemon.deployer.kubernetes.statefulset.deployer import StatefulSetDeployer
from fiaas_deploy_daemon.specs.models import (
    StatefulSetSpec,
    StatefulSetUpdateStrategySpec,
    StatefulSetVolumeClaimResourcesSpec,
    StatefulSetVolumeClaimSpec,
)


@pytest.fixture
def config():
    cfg = mock.create_autospec(Configuration([]), spec_set=True)
    cfg.pre_stop_delay = 0
    cfg.global_env = {}
    cfg.use_in_memory_emptydirs = False
    cfg.disable_deprecated_managed_env_vars = False
    cfg.enable_service_links = None
    cfg.dns_search_domains = []
    cfg.enable_service_account_per_app = False
    cfg.infrastructure = None
    cfg.log_format = "json"
    cfg.environment = None
    return cfg


def _stateful_app_spec(app_spec):
    claim = StatefulSetVolumeClaimSpec(
        name="data",
        mount_path="/data",
        storage_class_name=None,
        access_modes=["ReadWriteOnce"],
        annotations={},
        resources=StatefulSetVolumeClaimResourcesSpec(requests={"storage": "1Gi"}, limits=None),
    )
    statefulset_spec = StatefulSetSpec(
        enabled=True,
        service_name=None,
        pod_management_policy="OrderedReady",
        update_strategy=StatefulSetUpdateStrategySpec(type="RollingUpdate", rolling_update_partition=None),
        volume_claims=[claim],
    )
    return app_spec._replace(statefulset=statefulset_spec)


@mock.patch("fiaas_deploy_daemon.deployer.kubernetes.statefulset.deployer.StatefulSet")
@mock.patch("fiaas_deploy_daemon.deployer.kubernetes.statefulset.deployer.Deployment")
def test_creates_statefulset_and_deletes_deployment(mock_deployment, mock_statefulset, config, app_spec):
    app_spec = _stateful_app_spec(app_spec)
    mock_statefulset.get_or_create.return_value = mock.Mock(save=mock.Mock())

    deployer = StatefulSetDeployer(
        config,
        datadog=mock.Mock(),
        prometheus=mock.Mock(),
        deployment_secrets=mock.Mock(),
        owner_references=mock.Mock(),
        extension_hook=mock.Mock(),
    )

    deployer.deploy(app_spec, selector={"app": app_spec.name}, labels={"app": app_spec.name}, besteffort_qos_is_required=False)

    mock_deployment.delete.assert_called_with(app_spec.name, app_spec.namespace)
    mock_statefulset.get_or_create.assert_called_once()
    mock_statefulset.get_or_create.return_value.save.assert_called_once()


@mock.patch("fiaas_deploy_daemon.deployer.kubernetes.statefulset.deployer.StatefulSet")
def test_delete_called_when_statefulset_disabled(mock_statefulset, config, app_spec):
    deployer = StatefulSetDeployer(
        config,
        datadog=mock.Mock(),
        prometheus=mock.Mock(),
        deployment_secrets=mock.Mock(),
        owner_references=mock.Mock(),
        extension_hook=mock.Mock(),
    )

    deployer.deploy(app_spec, selector={"app": app_spec.name}, labels={}, besteffort_qos_is_required=False)

    mock_statefulset.delete.assert_called_with(app_spec.name, app_spec.namespace)
    mock_statefulset.get_or_create.assert_not_called()
