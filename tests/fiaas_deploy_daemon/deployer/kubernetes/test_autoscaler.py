#!/usr/bin/env python
# -*- coding: utf-8

import pytest

from fiaas_deploy_daemon.deployer.kubernetes.autoscaler import should_have_autoscaler, AutoscalerDeployer
from fiaas_deploy_daemon.specs.models import AutoscalerSpec, ResourcesSpec, ResourceRequirementSpec

LABELS = {"autoscaler_deployer": "pass through"}
AUTOSCALER_API = '/apis/autoscaling/v1/namespaces/default/horizontalpodautoscalers/'


def test_default_spec_should_create_no_autoscaler(app_spec):
    assert should_have_autoscaler(app_spec) is False


def test_autoscaler_enabled_and_1_replica_gives_no_autoscaler(app_spec):
    app_spec = app_spec._replace(autoscaler=AutoscalerSpec(enabled=True, min_replicas=2, cpu_threshold_percentage=50))
    app_spec = app_spec._replace(replicas=1)
    assert should_have_autoscaler(app_spec) is False


def test_autoscaler_enabled_and_2_replica_and_no_requested_cpu_gives_no_autoscaler(app_spec):
    app_spec = app_spec._replace(autoscaler=AutoscalerSpec(enabled=True, min_replicas=2, cpu_threshold_percentage=50))
    app_spec = app_spec._replace(replicas=2)

    assert should_have_autoscaler(app_spec) is False


def test_autoscaler_enabled_and_2_replica_and__requested_cpu_gives_autoscaler(app_spec):
    app_spec = app_spec._replace(autoscaler=AutoscalerSpec(enabled=True, min_replicas=2, cpu_threshold_percentage=50))
    app_spec = app_spec._replace(replicas=2)
    app_spec = app_spec._replace(resources=ResourcesSpec(limits=[], requests=ResourceRequirementSpec(cpu=1, memory=1)))

    assert should_have_autoscaler(app_spec)


class TestAutoscalerDeployer(object):
    @pytest.fixture
    def deployer(self):
        return AutoscalerDeployer()

    def test_new_autoscaler(self, deployer, post, app_spec):
        app_spec = app_spec._replace(
            autoscaler=AutoscalerSpec(enabled=True, min_replicas=2, cpu_threshold_percentage=50))
        app_spec = app_spec._replace(replicas=4)
        app_spec = app_spec._replace(
            resources=ResourcesSpec(limits=[], requests=ResourceRequirementSpec(cpu=1, memory=1)))

        deployer.deploy(app_spec, LABELS)

        expected_autoscaler = {
            'metadata': pytest.helpers.create_metadata('testapp', labels=LABELS),
            'spec': {
                "scaleTargetRef": {
                    "kind": "Deployment",
                    "name": "testapp",
                    "apiVersion": "extensions/v1beta1"
                },
                "minReplicas": 2,
                "maxReplicas": 4,
                "targetCPUUtilizationPercentage": 50
            },

        }
        pytest.helpers.assert_any_call(post, AUTOSCALER_API, expected_autoscaler)

    def test_new_autoscaler_with_custom_labels_and_annotations(self, deployer, post, app_spec):
        app_spec = app_spec._replace(
            autoscaler=AutoscalerSpec(enabled=True, min_replicas=2, cpu_threshold_percentage=50))
        app_spec = app_spec._replace(replicas=4)
        app_spec = app_spec._replace(
            resources=ResourcesSpec(limits=[], requests=ResourceRequirementSpec(cpu=1, memory=1)))
        app_spec = app_spec._replace(labels={"horizontal_pod_autoscaler": {"custom": "label"}},
                                     annotations={"horizontal_pod_autoscaler": {"custom": "annotation"}})

        deployer.deploy(app_spec, LABELS)

        expected_autoscaler = {
            'metadata': pytest.helpers.create_metadata('testapp', labels={"autoscaler_deployer": "pass through",
                                                                          "custom": "label"},
                                                       annotations={"custom": "annotation"}),
            'spec': {
                "scaleTargetRef": {
                    "kind": "Deployment",
                    "name": "testapp",
                    "apiVersion": "extensions/v1beta1"
                },
                "minReplicas": 2,
                "maxReplicas": 4,
                "targetCPUUtilizationPercentage": 50
            }
        }
        pytest.helpers.assert_any_call(post, AUTOSCALER_API, expected_autoscaler)

    def test_no_autoscaler_gives_no_post(self, deployer, post, app_spec):
        deployer.deploy(app_spec, LABELS)
        pytest.helpers.assert_no_calls(post)

    def test_no_autoscaler_gives_no_pust(self, deployer, put, app_spec):
        deployer.deploy(app_spec, LABELS)
        pytest.helpers.assert_no_calls(put)
