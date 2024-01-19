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
    def deployer(self, owner_references, extension_hook):
        return PodDisruptionBudgetDeployer(owner_references, extension_hook)

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

    def test_no_pdb_gives_no_post(self, deployer, post, app_spec):
        app_spec = app_spec._replace(
            autoscaler=AutoscalerSpec(enabled=True, min_replicas=1, max_replicas=1, cpu_threshold_percentage=50)
        )
        deployer.deploy(app_spec, SELECTOR, LABELS)
        pytest.helpers.assert_no_calls(post)

    def test_no_pdb_gives_no_put(self, deployer, put, app_spec):
        app_spec = app_spec._replace(
            autoscaler=AutoscalerSpec(enabled=True, min_replicas=1, max_replicas=1, cpu_threshold_percentage=50)
        )
        deployer.deploy(app_spec, SELECTOR, LABELS)
        pytest.helpers.assert_no_calls(put)
