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
from k8s.models.policy_v1_pod_disruption_budget import PodDisruptionBudget
from unittest.mock import create_autospec
from requests import Response
from utils import TypeMatcher

from fiaas_deploy_daemon import ExtensionHookCaller
from fiaas_deploy_daemon.config import Configuration
from fiaas_deploy_daemon.deployer.kubernetes.pod_disruption_budget import PodDisruptionBudgetDeployer
from fiaas_deploy_daemon.specs.models import (
    AutoscalerSpec,
)

LABELS = {"pod_disruption_budget": "pass through"}
SELECTOR = {"app": "testapp"}
PDB_API = "/apis/policy/v1/namespaces/default/poddisruptionbudgets/"


class TestPodDisruptionBudgetDeployer(object):
    @pytest.fixture
    def extension_hook(self):
        return create_autospec(ExtensionHookCaller, spec_set=True, instance=True)

    @pytest.fixture
    def deployer(self, owner_references, extension_hook, config):
        return PodDisruptionBudgetDeployer(owner_references, extension_hook, config)

    @pytest.fixture
    def config(self):
        config = create_autospec(Configuration([]), spec_set=True)
        config.pdb_max_unavailable = 1
        return config

    @pytest.mark.usefixtures("get")
    def test_new_pdb(self, deployer, post, app_spec, owner_references, extension_hook):
        expected_pdb = {
            "metadata": pytest.helpers.create_metadata("testapp", labels=LABELS),
            "spec": {
                "maxUnavailable": 1,
                "selector": {"matchExpressions": [], "matchLabels": {"app": "testapp"}},
            },
        }
        mock_response = create_autospec(Response)
        mock_response.json.return_value = expected_pdb
        post.return_value = mock_response

        deployer.deploy(app_spec, SELECTOR, LABELS)

        pytest.helpers.assert_any_call(post, PDB_API, expected_pdb)
        owner_references.apply.assert_called_once_with(TypeMatcher(PodDisruptionBudget), app_spec)
        extension_hook.apply.assert_called_once_with(TypeMatcher(PodDisruptionBudget), app_spec)

    def test_no_pdb_gives_no_post(self, deployer: PodDisruptionBudgetDeployer, delete, post, app_spec):
        app_spec = app_spec._replace(
            autoscaler=AutoscalerSpec(enabled=True, min_replicas=1, max_replicas=1, cpu_threshold_percentage=50)
        )
        deployer.deploy(app_spec, SELECTOR, LABELS)
        delete.assert_called_with(PDB_API + app_spec.name)
        pytest.helpers.assert_no_calls(post)

    def test_zero_replicas_no_pdb_gives_no_post(self, deployer: PodDisruptionBudgetDeployer, delete, post, app_spec):
        app_spec = app_spec._replace(
            autoscaler=AutoscalerSpec(enabled=True, min_replicas=0, max_replicas=0, cpu_threshold_percentage=50)
        )
        deployer.deploy(app_spec, SELECTOR, LABELS)
        delete.assert_called_with(PDB_API + app_spec.name)
        pytest.helpers.assert_no_calls(post)

    def test_no_pdb_gives_no_put(self, deployer, delete, put, app_spec):
        app_spec = app_spec._replace(
            autoscaler=AutoscalerSpec(enabled=True, min_replicas=1, max_replicas=1, cpu_threshold_percentage=50)
        )
        deployer.deploy(app_spec, SELECTOR, LABELS)
        delete.assert_called_with(PDB_API + app_spec.name)
        pytest.helpers.assert_no_calls(put)

    @pytest.mark.usefixtures("get")
    def test_setting_max_int(self, deployer, post, app_spec, owner_references, extension_hook):
        app_spec = app_spec._replace(
            autoscaler=AutoscalerSpec(enabled=True, min_replicas=4, max_replicas=6, cpu_threshold_percentage=50)
        )
        deployer.max_unavailable = 2
        expected_pdb = {
            "metadata": pytest.helpers.create_metadata("testapp", labels=LABELS),
            "spec": {
                "maxUnavailable": 2,
                "selector": {"matchExpressions": [], "matchLabels": {"app": "testapp"}},
            },
        }
        mock_response = create_autospec(Response)
        mock_response.json.return_value = expected_pdb
        post.return_value = mock_response

        deployer.deploy(app_spec, SELECTOR, LABELS)

        pytest.helpers.assert_any_call(post, PDB_API, expected_pdb)
        owner_references.apply.assert_called_once_with(TypeMatcher(PodDisruptionBudget), app_spec)
        extension_hook.apply.assert_called_once_with(TypeMatcher(PodDisruptionBudget), app_spec)

    def test_no_pdb_max_over_min(self, deployer: PodDisruptionBudgetDeployer, delete, post, app_spec):
        app_spec = app_spec._replace(
            autoscaler=AutoscalerSpec(enabled=True, min_replicas=1, max_replicas=4, cpu_threshold_percentage=50)
        )
        deployer.deploy(app_spec, SELECTOR, LABELS)
        delete.assert_called_with(PDB_API + app_spec.name)
        pytest.helpers.assert_no_calls(post)

    @pytest.mark.usefixtures("get")
    def test_setting_max_str(self, deployer, post, app_spec, owner_references, extension_hook):
        app_spec = app_spec._replace(
            autoscaler=AutoscalerSpec(enabled=True, min_replicas=4, max_replicas=6, cpu_threshold_percentage=50)
        )
        deployer.max_unavailable = "20%"
        expected_pdb = {
            "metadata": pytest.helpers.create_metadata("testapp", labels=LABELS),
            "spec": {
                "maxUnavailable": "20%",
                "selector": {"matchExpressions": [], "matchLabels": {"app": "testapp"}},
            },
        }
        mock_response = create_autospec(Response)
        mock_response.json.return_value = expected_pdb
        post.return_value = mock_response

        deployer.deploy(app_spec, SELECTOR, LABELS)

        pytest.helpers.assert_any_call(post, PDB_API, expected_pdb)
        owner_references.apply.assert_called_once_with(TypeMatcher(PodDisruptionBudget), app_spec)
        extension_hook.apply.assert_called_once_with(TypeMatcher(PodDisruptionBudget), app_spec)
