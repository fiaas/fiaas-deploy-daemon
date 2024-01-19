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

from dataclasses import dataclass

from unittest import mock
import pytest

from fiaas_deploy_daemon import Configuration
from fiaas_deploy_daemon.crd.types import AdditionalLabelsOrAnnotations
from fiaas_deploy_daemon.specs.factory import SpecFactory, InvalidConfiguration
from fiaas_deploy_daemon.specs.lookup import _Lookup
from fiaas_deploy_daemon.specs.v3.factory import Factory

IMAGE = "finntech/docker-image:some-version"
NAME = "application-name"
NAMESPACE = "namespace-value"
UID = "23840085-8ab6-11ea-b4f9-02a852666faa"

TEST_DATA = {
    "v3minimal": {
        "uid": UID,
        "namespace": NAMESPACE,
        "autoscaler.enabled": True,
        "autoscaler.min_replicas": 2,
        "autoscaler.max_replicas": 5,
        "autoscaler.cpu_threshold_percentage": 50,
        "prometheus.enabled": True,
        "prometheus.port": "http",
        "prometheus.path": "/_/metrics",
        "resources.limits.memory": "512Mi",
        "resources.limits.cpu": "400m",
        "resources.requests.memory": "256Mi",
        "resources.requests.cpu": "200m",
        "ports[0].protocol": "http",
        "ports[0].name": "http",
        "ports[0].port": 80,
        "ports[0].target_port": 8080,
        "health_checks.liveness.http.path": "/_/health",
        "health_checks.liveness.http.port": "http",
        "health_checks.liveness.http.http_headers": {},
        "health_checks.liveness.initial_delay_seconds": 10,
        "health_checks.liveness.period_seconds": 10,
        "health_checks.liveness.success_threshold": 1,
        "health_checks.liveness.failure_threshold": 3,
        "health_checks.liveness.timeout_seconds": 1,
        "health_checks.liveness.execute": None,
        "health_checks.liveness.tcp": None,
        "health_checks.readiness.http.path": "/_/ready",
        "health_checks.readiness.http.port": "http",
        "health_checks.readiness.http.http_headers": {},
        "health_checks.readiness.initial_delay_seconds": 10,
        "health_checks.readiness.period_seconds": 10,
        "health_checks.readiness.success_threshold": 1,
        "health_checks.readiness.failure_threshold": 3,
        "health_checks.readiness.timeout_seconds": 1,
        "health_checks.readiness.execute": None,
        "health_checks.readiness.tcp": None,
        "labels.deployment": {},
        "labels.horizontal_pod_autoscaler": {},
        "labels.service": {},
        "labels.service_account": {},
        "labels.ingress": {},
        "labels.pod": {},
        "annotations.deployment": {},
        "annotations.horizontal_pod_autoscaler": {},
        "annotations.service": {},
        "annotations.service_account": {},
        "annotations.ingress": {},
        "annotations.pod": {},
        "ingresses[0].host": None,
        "ingresses[0].pathmappings[0].path": "/",
        "ingresses[0].pathmappings[0].port": 80,
        "secrets_in_environment": False,
        "admin_access": False,
        "strongbox.enabled": False,
        "strongbox.iam_role": None,
        "strongbox.groups": None,
        "strongbox.aws_region": "eu-west-1",
    },
    "autoscaling_disabled": {
        "autoscaler.enabled": False,
        "autoscaler.min_replicas": 3,
        "autoscaler.max_replicas": 3,
        "autoscaler.cpu_threshold_percentage": 50,
    },
    "autoscaling_max_less_than_min": {
        "autoscaler.enabled": False,
        "autoscaler.min_replicas": 1,
        "autoscaler.max_replicas": 1,
        "autoscaler.cpu_threshold_percentage": 50,
    },
    "multiple_hosts_multiple_paths": {
        "ingresses[0].host": None,
        "ingresses[0].pathmappings[0].path": "/0noport",
        "ingresses[0].pathmappings[0].port": 80,
        "ingresses[0].pathmappings[1].path": "/0portname",
        "ingresses[0].pathmappings[1].port": 80,
        "ingresses[0].pathmappings[2].path": "/0portnumber",
        "ingresses[0].pathmappings[2].port": 80,
        "ingresses[1].host": "foo.example.com",
        "ingresses[1].pathmappings[0].path": "/1noport",
        "ingresses[1].pathmappings[0].port": 80,
        "ingresses[1].pathmappings[1].path": "/1portname",
        "ingresses[1].pathmappings[1].port": 80,
        "ingresses[1].pathmappings[2].path": "/1portnumber",
        "ingresses[1].pathmappings[2].port": 80,
        "ingresses[2].host": "bar.example.com",
        "ingresses[2].pathmappings[0].path": "/2noport",
        "ingresses[2].pathmappings[0].port": 80,
        "ingresses[2].pathmappings[1].path": "/2portname",
        "ingresses[2].pathmappings[1].port": 80,
        "ingresses[2].pathmappings[2].path": "/2portnumber",
        "ingresses[2].pathmappings[2].port": 80,
    },
    "exec_check": {
        "health_checks.liveness.execute.command": "/bin/alive",
        "health_checks.readiness.execute.command": "/bin/ready",
        "health_checks.liveness.tcp": None,
        "health_checks.readiness.tcp": None,
        "health_checks.liveness.http": None,
        "health_checks.readiness.http": None,
    },
    "single_explicit_tcp_port_default_healthcheck": {
        "ports[0].protocol": "tcp",
        "ports[0].name": "thing",
        "ports[0].port": 1337,
        "ports[0].target_port": 31337,
        "health_checks.liveness.execute": None,
        "health_checks.readiness.execute": None,
        "health_checks.liveness.tcp.port": "thing",
        "health_checks.readiness.tcp.port": "thing",
        "health_checks.liveness.http": None,
        "health_checks.readiness.http": None,
    },
    "single_explicit_http_port_default_health_check": {
        "ports[0].protocol": "http",
        "ports[0].name": "thing",
        "ports[0].port": 1337,
        "ports[0].target_port": 31337,
        "health_checks.liveness.execute": None,
        "health_checks.readiness.execute": None,
        "health_checks.liveness.tcp": None,
        "health_checks.readiness.tcp": None,
        "health_checks.readiness.http.path": "/_/ready",
        "health_checks.readiness.http.port": "thing",
        "health_checks.readiness.http.http_headers": {},
        "health_checks.liveness.http.path": "/_/health",
        "health_checks.liveness.http.port": "thing",
        "health_checks.liveness.http.http_headers": {},
    },
    "multiple_tcp_ports": {
        "ports[0].protocol": "tcp",
        "ports[0].name": "a",
        "ports[0].port": 1337,
        "ports[0].target_port": 31337,
        "ports[1].protocol": "tcp",
        "ports[1].name": "b",
        "ports[1].port": 1338,
        "ports[1].target_port": 31338,
        "health_checks.liveness.execute": None,
        "health_checks.readiness.execute": None,
        "health_checks.liveness.tcp.port": "a",
        "health_checks.readiness.tcp.port": "b",
        "health_checks.liveness.http": None,
        "health_checks.readiness.http": None,
    },
    "multiple_http_ports": {
        "ports[0].protocol": "http",
        "ports[0].name": "a",
        "ports[0].port": 1337,
        "ports[0].target_port": 31337,
        "ports[1].protocol": "http",
        "ports[1].name": "b",
        "ports[1].port": 1338,
        "ports[1].target_port": 31338,
        "health_checks.liveness.execute": None,
        "health_checks.readiness.execute": None,
        "health_checks.liveness.tcp": None,
        "health_checks.readiness.tcp": None,
        "health_checks.readiness.http.path": "/b",
        "health_checks.readiness.http.port": "b",
        "health_checks.readiness.http.http_headers": {},
        "health_checks.liveness.http.path": "/a",
        "health_checks.liveness.http.port": "a",
        "health_checks.liveness.http.http_headers": {},
    },
    "health_check_http_headers_readiness_is_liveness": {
        "ports[0].protocol": "http",
        "ports[0].name": "thing",
        "ports[0].port": 1337,
        "ports[0].target_port": 31337,
        "health_checks.liveness.execute": None,
        "health_checks.readiness.execute": None,
        "health_checks.liveness.tcp": None,
        "health_checks.readiness.tcp": None,
        "health_checks.readiness.http.path": "/",
        "health_checks.readiness.http.port": "thing",
        "health_checks.readiness.http.http_headers": {"X-Custom-Header": "stuff"},
        "health_checks.liveness.http.path": "/",
        "health_checks.liveness.http.port": "thing",
        "health_checks.liveness.http.http_headers": {"X-Custom-Header": "stuff"},
    },
    "ports_empty_list": {
        "ports": [],
    },
    "labels_and_annotations": {
        "labels.deployment": {"a": "b", "c": "d"},
        "labels.horizontal_pod_autoscaler": {"e": "f", "g": "h"},
        "labels.ingress": {"i": "j", "k": "l"},
        "labels.service": {"m": "n", "o": "p"},
        "labels.pod": {"q": "r", "s": "u"},
        "annotations.deployment": {"m": "n", "o": "p"},
        "annotations.horizontal_pod_autoscaler": {"i": "j", "k": "l"},
        "annotations.ingress": {"e": "f", "g": "h"},
        "annotations.service": {"a": "b", "c": "d"},
        "annotations.pod": {"x": "y", "z": "y"},
    },
    "full": {
        "namespace": NAMESPACE,
        "autoscaler.enabled": True,
        "autoscaler.min_replicas": 10,
        "autoscaler.max_replicas": 20,
        "autoscaler.cpu_threshold_percentage": 60,
        "ingresses[0].host": "www.example.com",
        "ingresses[0].pathmappings[0].path": "/a",
        "ingresses[0].pathmappings[0].port": 1337,
        "health_checks.liveness.http.path": "/health",
        "health_checks.liveness.http.port": "a",
        "health_checks.liveness.http.http_headers": {"X-Custom-Header": "liveness-stuff"},
        "health_checks.readiness.tcp.port": "b",
        "health_checks.readiness.initial_delay_seconds": 5,
        "health_checks.readiness.period_seconds": 5,
        "health_checks.readiness.success_threshold": 2,
        "health_checks.readiness.failure_threshold": 6,
        "health_checks.readiness.timeout_seconds": 2,
        "resources.limits.memory": "1024Mi",
        "resources.limits.cpu": 2,
        "resources.requests.memory": "512Mi",
        "resources.requests.cpu": "500m",
        "prometheus.enabled": True,
        "prometheus.port": "a",
        "prometheus.path": "/prometheus-metrics-here",
        "datadog.enabled": True,
        "datadog.tags": {"tag1": "value1", "tag2": "value2"},
        "ports[0].protocol": "http",
        "ports[0].name": "a",
        "ports[0].port": 1337,
        "ports[0].target_port": 31337,
        "ports[1].protocol": "tcp",
        "ports[1].name": "b",
        "ports[1].port": 1338,
        "ports[1].target_port": 31338,
        "labels.deployment": {"a": "b", "c": "d"},
        "labels.horizontal_pod_autoscaler": {"e": "f", "g": "h"},
        "labels.ingress": {"i": "j", "k": "l"},
        "labels.service": {"m": "n", "o": "p"},
        "labels.pod": {"q": "r", "s": "u"},
        "annotations.deployment": {"m": "n", "o": "p"},
        "annotations.horizontal_pod_autoscaler": {"i": "j", "k": "l"},
        "annotations.ingress": {"e": "f", "g": "h"},
        "annotations.service": {"a": "b", "c": "d"},
        "annotations.pod": {"x": "y", "z": "y"},
        "secrets_in_environment": True,
        "admin_access": True,
        "strongbox.enabled": True,
        "strongbox.iam_role": "arn:aws:iam::12345678:role/the-role-name",
        "strongbox.groups[0]": "secretgroup1",
        "strongbox.groups[1]": "secretgroup2",
    },
    "liveness_exec_readiness_http": {
        "health_checks.liveness.execute.command": "/bin/alive",
        "health_checks.liveness.tcp": None,
        "health_checks.liveness.http": None,
        "health_checks.readiness.http.path": "/ready",
        "health_checks.readiness.http.port": "http",
        "health_checks.readiness.execute": None,
        "health_checks.readiness.tcp": None,
    },
    "liveness_tcp_readiness_http": {
        "health_checks.liveness.tcp.port": "liveness-port",
        "health_checks.liveness.execute": None,
        "health_checks.liveness.http": None,
        "health_checks.readiness.http.path": "/ready",
        "health_checks.readiness.http.port": "http",
        "health_checks.readiness.execute": None,
        "health_checks.readiness.tcp": None,
    },
    "default_tcp_healthcheck": {
        "ports[0].protocol": "tcp",
        "ports[0].name": "liveness-port",
        "ports[0].port": 8889,
        "ports[0].target_port": 8882,
        "health_checks.liveness.execute": None,
        "health_checks.readiness.execute": None,
        "health_checks.liveness.tcp.port": "liveness-port",
        "health_checks.readiness.tcp.port": "liveness-port",
        "health_checks.liveness.http": None,
        "health_checks.readiness.http": None,
    },
    "strongbox": {
        "strongbox.iam_role": "arn:aws:iam::12345678:role/the-role-name",
        "strongbox.aws_region": "eu-central-1",
        "strongbox.groups[0]": "secretgroup1",
        "strongbox.groups[1]": "secretgroup2",
        "strongbox.groups[2]": "secretgroup3",
    },
    "ingress_empty": {
        "ingresses": [],
    },
    "tls_enabled": {
        "ingress_tls.enabled": True,
    },
    "tls_enabled_cert_issuer": {"ingress_tls.enabled": True, "ingress_tls.certificate_issuer": "myissuer"},
    "secrets": {
        "secrets[0].type": "parameter-store",
        "secrets[0].parameters": {"AWS_REGION": "eu-central-1", "SECRET_PATH": "some-param"},
        "secrets[0].annotations": {
            "iam.amazonaws.com/role": "arn:aws:iam::12345678:role/the-role-name",
            "some.other/annotation": "annotation-value",
        },
    },
    "secrets_strongbox": {
        "secrets[0].type": "strongbox",
        "secrets[0].parameters": {
            "AWS_REGION": "eu-central-1",
            "SECRET_GROUPS": "secretgroup1,secretgroup2,secretgroup3",
        },
        "secrets[0].annotations": {"iam.amazonaws.com/role": "arn:aws:iam::12345678:role/the-role-name"},
    },
}


@dataclass
class SpecAttributeTestCase:
    filename: str
    attribute: str
    value: any

    @property
    def test_id(self):
        return "{}/{}=={}".format(self.filename, self.attribute.replace(".", "_"), repr(self.value).replace(".", "_"))


class TestFactory(object):
    @pytest.fixture
    def factory(self):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        return SpecFactory(Factory(), {}, config)

    @pytest.mark.parametrize("filename", ("v3minimal",))
    def test_name_and_image(self, load_app_config_testdata, factory, filename):
        app_spec = factory(
            UID,
            NAME,
            IMAGE,
            load_app_config_testdata(filename),
            ["IO"],
            ["foo"],
            "deployment_id",
            NAMESPACE,
            None,
            None,
        )
        assert app_spec.name == NAME
        assert app_spec.image == IMAGE

    @pytest.mark.parametrize(
        "filename",
        (
            "invalid_no_health_check_defined_http",
            "invalid_no_health_check_defined_tcp",
            "invalid_ingress_port_number",
            "invalid_ingress_port_name",
        ),
    )
    def test_invalid_configuration(self, load_app_config_testdata, factory, filename):
        with pytest.raises(InvalidConfiguration):
            factory(
                UID,
                NAME,
                IMAGE,
                load_app_config_testdata(filename),
                ["IO"],
                ["foo"],
                "deployment_id",
                NAMESPACE,
                None,
                None,
            )

    @pytest.mark.parametrize(
        "filename,attribute,value",
        (
            ("v3minimal", "annotations.deployment", {"global/annotation": "true", "deployment/annotation": "true"}),
            (
                "labels_and_annotations",
                "annotations.pod",
                {
                    "global/annotation": "true",
                    "pod/annotation": "true",
                    "x": "y",
                    "z": "override",
                },
            ),
            (
                "labels_and_annotations",
                "labels.pod",
                {
                    "global/label": "true",
                    "pod/label": "true",
                    "q": "r",
                    "s": "override",
                },
            ),
            ("labels_and_annotations", "labels.status", {"global/label": "true", "status/label": "true"}),
            (
                "labels_and_annotations",
                "labels.pod_disruption_budget",
                {"global/label": "true", "pod-disruption-budget/label": "true"}
            ),
            (
                "labels_and_annotations",
                "annotations.pod_disruption_budget",
                {"global/annotation": "true", "pod-disruption-budget/annotation": "true"}
            ),
        ),
    )
    def test_additional_labels_and_annotations(self, load_app_config_testdata, factory, filename, attribute, value):
        additional_labels = AdditionalLabelsOrAnnotations(
            _global={"global/label": "true"},
            deployment={"deployment/label": "true"},
            horizontal_pod_autoscaler={"horizontal-pod-autoscaler/label": "true"},
            ingress={"ingress/label": "true"},
            service={"service/label": "true"},
            pod={"pod/label": "true", "s": "override"},
            status={"status/label": "true"},
            pod_disruption_budget={"pod-disruption-budget/label": "true"},
        )
        additional_annotations = AdditionalLabelsOrAnnotations(
            _global={"global/annotation": "true"},
            deployment={"deployment/annotation": "true"},
            horizontal_pod_autoscaler={"horizontal-pod-autoscaler/annotation": "true"},
            ingress={"ingress/annotation": "true"},
            service={"service/annotation": "true"},
            pod={"pod/annotation": "true", "z": "override"},
            status={"status/annotation": "true"},
            pod_disruption_budget={"pod-disruption-budget/annotation": "true"},
        )
        app_spec = factory(
            UID,
            NAME,
            IMAGE,
            load_app_config_testdata(filename),
            [],
            [],
            "deployment_id",
            NAMESPACE,
            additional_labels,
            additional_annotations,
        )
        assert app_spec is not None
        code = "app_spec.%s" % attribute
        actual = eval(code)
        assert isinstance(actual, _Lookup) is False  # _Lookup objects should not leak to AppSpec
        assert actual == value

    @pytest.mark.parametrize(
        "testcase",
        (
            SpecAttributeTestCase(filename, attribute, TEST_DATA[filename][attribute])
            for filename in TEST_DATA
            for attribute in TEST_DATA[filename]
        ),
        ids=lambda testcase: testcase.test_id
    )
    def test(self, load_app_config_testdata, factory, testcase):
        app_spec = factory(
            UID,
            NAME,
            IMAGE,
            load_app_config_testdata(testcase.filename),
            ["IO"],
            ["foo"],
            "deployment_id",
            NAMESPACE,
            None,
            None,
        )
        assert app_spec is not None
        code = "app_spec.%s" % testcase.attribute
        assert app_spec.secrets is not None
        actual = eval(code)
        assert isinstance(actual, _Lookup) is False  # _Lookup objects should not leak to AppSpec
        assert actual == testcase.value
