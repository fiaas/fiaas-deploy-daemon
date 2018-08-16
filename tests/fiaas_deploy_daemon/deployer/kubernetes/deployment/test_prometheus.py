#!/usr/bin/env python
# -*- coding: utf-8
from copy import deepcopy

import mock
import pytest
from k8s.models.common import ObjectMeta
from k8s.models.deployment import Deployment, DeploymentSpec
from k8s.models.pod import PodTemplateSpec

from fiaas_deploy_daemon.deployer.kubernetes.deployment.prometheus import Prometheus


class TestPrometheus(object):
    @pytest.fixture
    def prometheus(self):
        return Prometheus()

    @pytest.fixture
    def deployment(self):
        metadata = ObjectMeta(annotations={"dummy": "annotations"})
        pod_template_spec = PodTemplateSpec(metadata=metadata)
        deployment_spec = DeploymentSpec(template=pod_template_spec)
        return Deployment(spec=deployment_spec)

    def test_noop_when_not_enabled(self, prometheus, app_spec, deployment):
        prometheus_spec = app_spec.prometheus._replace(enabled=False)
        app_spec = app_spec._replace(prometheus=prometheus_spec)
        expected = deepcopy(deployment)
        prometheus.apply(deployment, app_spec)
        assert expected == deployment

    @pytest.mark.parametrize("port,expected_port,path", (
            ("9999", "9999", "/_/metrics"),
            ("8080", "8080", "/internal-backstage/prometheus"),
            ("http", "8080", "/awesome"),
    ))
    def test_adds_annotations_when_enabled(self, prometheus, app_spec, deployment, port, expected_port, path):
        prometheus_spec = app_spec.prometheus._replace(port=port, path=path)
        app_spec = app_spec._replace(prometheus=prometheus_spec)
        original_annotations = deepcopy(deployment.spec.template.metadata.annotations)
        prometheus.apply(deployment, app_spec)
        expected = {
            "prometheus.io/scrape": "true",
            "prometheus.io/port": expected_port,
            "prometheus.io/path": path
        }
        annotations = deployment.spec.template.metadata.annotations
        for key in expected:
            assert expected[key] == annotations[key]
        for key in original_annotations:
            assert original_annotations[key] == annotations[key]

    def test_sets_empty_annotations_when_invalid(self, prometheus, app_spec, deployment):
        prometheus_spec = app_spec.prometheus._replace(port="invalid")
        app_spec = app_spec._replace(prometheus=prometheus_spec)
        expected = deepcopy(deployment)
        prometheus.apply(deployment, app_spec)
        assert expected == deployment

    def test_logs_exception_when_invalid(self, prometheus, app_spec, deployment):
        prometheus_spec = app_spec.prometheus._replace(port="invalid")
        app_spec = app_spec._replace(prometheus=prometheus_spec)
        with mock.patch("fiaas_deploy_daemon.deployer.kubernetes.deployment.prometheus.LOG") as log_mock:
            prometheus.apply(deployment, app_spec)
            log_mock.error.assert_called_once_with("Invalid prometheus configuration for %s", app_spec.name)
