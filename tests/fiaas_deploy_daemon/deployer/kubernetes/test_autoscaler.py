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
from k8s.models.autoscaler import HorizontalPodAutoscaler
from unittest.mock import create_autospec
from requests import Response
from utils import TypeMatcher

from fiaas_deploy_daemon import ExtensionHookCaller
from fiaas_deploy_daemon.deployer.kubernetes.autoscaler import should_have_autoscaler, AutoscalerDeployer
from fiaas_deploy_daemon.specs.models import (
    AutoscalerSpec,
    ResourcesSpec,
    ResourceRequirementSpec,
    LabelAndAnnotationSpec,
)

LABELS = {"autoscaler_deployer": "pass through"}
AUTOSCALER_API = "/apis/autoscaling/v1/namespaces/default/horizontalpodautoscalers/"


def test_default_spec_should_create_no_autoscaler(app_spec):
    assert should_have_autoscaler(app_spec) is False


def test_autoscaler_enabled_and_1_replica_gives_no_autoscaler(app_spec):
    app_spec = app_spec._replace(
        autoscaler=AutoscalerSpec(enabled=True, min_replicas=1, max_replicas=1, cpu_threshold_percentage=50)
    )
    assert should_have_autoscaler(app_spec) is False


def test_autoscaler_enabled_and_2_max_replicas_and_no_requested_cpu_gives_no_autoscaler(app_spec):
    app_spec = app_spec._replace(
        autoscaler=AutoscalerSpec(enabled=True, min_replicas=1, max_replicas=2, cpu_threshold_percentage=50)
    )

    assert should_have_autoscaler(app_spec) is False


def test_autoscaler_enabled_and_2_max_replicas_and__requested_cpu_gives_autoscaler(app_spec):
    app_spec = app_spec._replace(
        autoscaler=AutoscalerSpec(enabled=True, min_replicas=1, max_replicas=2, cpu_threshold_percentage=50)
    )
    app_spec = app_spec._replace(resources=ResourcesSpec(limits=[], requests=ResourceRequirementSpec(cpu=1, memory=1)))

    assert should_have_autoscaler(app_spec)


class TestAutoscalerDeployer(object):
    @pytest.fixture
    def extension_hook(self):
        return create_autospec(ExtensionHookCaller, spec_set=True, instance=True)

    @pytest.fixture
    def deployer(self, owner_references, extension_hook):
        return AutoscalerDeployer(owner_references, extension_hook)

    @pytest.mark.usefixtures("get")
    def test_new_autoscaler(self, deployer, post, app_spec, owner_references, extension_hook):
        app_spec = app_spec._replace(
            autoscaler=AutoscalerSpec(enabled=True, min_replicas=2, max_replicas=4, cpu_threshold_percentage=50)
        )
        app_spec = app_spec._replace(
            resources=ResourcesSpec(limits=[], requests=ResourceRequirementSpec(cpu=1, memory=1))
        )

        expected_autoscaler = {
            "metadata": pytest.helpers.create_metadata("testapp", labels=LABELS),
            "spec": {
                "scaleTargetRef": {"kind": "Deployment", "name": "testapp", "apiVersion": "apps/v1"},
                "minReplicas": 2,
                "maxReplicas": 4,
                "targetCPUUtilizationPercentage": 50,
            },
        }
        mock_response = create_autospec(Response)
        mock_response.json.return_value = expected_autoscaler
        post.return_value = mock_response

        deployer.deploy(app_spec, LABELS)

        pytest.helpers.assert_any_call(post, AUTOSCALER_API, expected_autoscaler)
        owner_references.apply.assert_called_once_with(TypeMatcher(HorizontalPodAutoscaler), app_spec)
        extension_hook.apply.assert_called_once_with(TypeMatcher(HorizontalPodAutoscaler), app_spec)

    @pytest.mark.usefixtures("get")
    def test_new_autoscaler_with_custom_labels_and_annotations(
        self, deployer, post, app_spec, owner_references, extension_hook
    ):
        app_spec = app_spec._replace(
            autoscaler=AutoscalerSpec(enabled=True, min_replicas=2, max_replicas=4, cpu_threshold_percentage=50)
        )
        app_spec = app_spec._replace(
            resources=ResourcesSpec(limits=[], requests=ResourceRequirementSpec(cpu=1, memory=1))
        )
        labels = LabelAndAnnotationSpec(
            deployment={},
            horizontal_pod_autoscaler={"custom": "label"},
            ingress={},
            service={},
            pod={},
            status={},
            service_account={},
            pod_disruption_budget={},
            role_binding={},
        )
        annotations = LabelAndAnnotationSpec(
            deployment={},
            horizontal_pod_autoscaler={"custom": "annotation"},
            ingress={},
            service={},
            pod={},
            status={},
            service_account={},
            pod_disruption_budget={},
            role_binding={},
        )
        app_spec = app_spec._replace(labels=labels, annotations=annotations)

        expected_autoscaler = {
            "metadata": pytest.helpers.create_metadata(
                "testapp",
                labels={"autoscaler_deployer": "pass through", "custom": "label"},
                annotations={"custom": "annotation"},
            ),
            "spec": {
                "scaleTargetRef": {"kind": "Deployment", "name": "testapp", "apiVersion": "apps/v1"},
                "minReplicas": 2,
                "maxReplicas": 4,
                "targetCPUUtilizationPercentage": 50,
            },
        }
        mock_response = create_autospec(Response)
        mock_response.json.return_value = expected_autoscaler
        post.return_value = mock_response

        deployer.deploy(app_spec, LABELS)

        pytest.helpers.assert_any_call(post, AUTOSCALER_API, expected_autoscaler)
        owner_references.apply.assert_called_once_with(TypeMatcher(HorizontalPodAutoscaler), app_spec)
        extension_hook.apply.assert_called_once_with(TypeMatcher(HorizontalPodAutoscaler), app_spec)

    def test_no_autoscaler_gives_no_post(self, deployer, delete, post, app_spec):
        deployer.deploy(app_spec, LABELS)
        delete.assert_called_with(AUTOSCALER_API + app_spec.name)
        pytest.helpers.assert_no_calls(post)

    def test_no_autoscaler_gives_no_put(self, deployer, delete, put, app_spec):
        deployer.deploy(app_spec, LABELS)
        delete.assert_called_with(AUTOSCALER_API + app_spec.name)
        pytest.helpers.assert_no_calls(put)
