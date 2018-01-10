#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import, unicode_literals

import pytest
import mock

from fiaas_deploy_daemon import Configuration
from fiaas_deploy_daemon.specs.v3.factory import Factory
from fiaas_deploy_daemon.specs.factory import SpecFactory, InvalidConfiguration
from fiaas_deploy_daemon.specs.lookup import _Lookup

IMAGE = "finntech/docker-image:some-version"
NAME = "application-name"
NAMESPACE = "namespace-value"

TEST_DATA = {
    "v3minimal": {
        "namespace": NAMESPACE,
        "replicas": 5,
        "autoscaler.enabled": True,
        "autoscaler.min_replicas": 2,
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
        "health_checks.liveness.timeout_seconds": 1,
        "health_checks.liveness.execute": None,
        "health_checks.liveness.tcp": None,
        "health_checks.readiness.http.path": "/_/ready",
        "health_checks.readiness.http.port": "http",
        "health_checks.readiness.http.http_headers": {},
        "health_checks.readiness.initial_delay_seconds": 10,
        "health_checks.readiness.period_seconds": 10,
        "health_checks.readiness.success_threshold": 1,
        "health_checks.readiness.timeout_seconds": 1,
        "health_checks.readiness.execute": None,
        "health_checks.readiness.tcp": None,
        "labels.deployment": {},
        "labels.horizontal_pod_autoscaler": {},
        "labels.service": {},
        "labels.ingress": {},
        "labels.pod": {},
        "annotations.deployment": {},
        "annotations.horizontal_pod_autoscaler": {},
        "annotations.service": {},
        "annotations.ingress": {},
        "annotations.pod": {},
        "ingresses[0].host": None,
        "ingresses[0].pathmappings[0].path": "/",
        "ingresses[0].pathmappings[0].port": 80,
        "secrets_in_environment": False,
        "admin_access": False,
    },
    "autoscaling_disabled": {
        "replicas": 3,
        "autoscaler.enabled": False,
        "autoscaler.min_replicas": 3,
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
        "ports[0].protocol": "http",
        "ports[0].name": "http",
        "ports[0].port": 80,
        "ports[0].target_port": 8080,
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
        "replicas": 20,
        "autoscaler.enabled": True,
        "autoscaler.min_replicas": 10,
        "autoscaler.cpu_threshold_percentage": 60,
        "ingresses[0].host": "www.example.com",
        "ingresses[0].pathmappings[0].path": "/a",
        "ingresses[0].pathmappings[0].port": 1337,
        "health_checks.liveness.http.path": "/health",
        "health_checks.liveness.http.port": "a",
        "health_checks.liveness.http.http_headers": {"X-Custom-Header": "liveness-stuff"},
        "health_checks.readiness.tcp.port": "b",
        "resources.limits.memory": "1024Mi",
        "resources.limits.cpu": 2,
        "resources.requests.memory": "512Mi",
        "resources.requests.cpu": "500m",
        "prometheus.enabled": True,
        "prometheus.port": "a",
        "prometheus.path": "/prometheus-metrics-here",
        "datadog": True,
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
}


def pytest_generate_tests(metafunc):
    fixtures = ("filename", "attribute", "value")
    if metafunc.cls == TestFactory and metafunc.function.__name__ == "test" \
       and all(fixname in metafunc.fixturenames for fixname in fixtures):
        for filename in TEST_DATA:
            for attribute in TEST_DATA[filename]:
                value = TEST_DATA[filename][attribute]
                fixture_args = {"filename": filename, "attribute": attribute, "value": value}
                metafunc.addcall(fixture_args, "{}/{}=={}".format(filename, attribute.replace(".", "_"),
                                                                  repr(value).replace(".", "_")))


class TestFactory(object):
    @pytest.fixture
    def factory(self):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        return SpecFactory(Factory(), {}, config)

    @pytest.mark.parametrize("filename", (
            "v3minimal",
    ))
    def test_name_and_image(self, load_app_config_testdata, factory, filename):
        app_spec = factory(NAME, IMAGE, load_app_config_testdata(filename), "IO", "foo", "deployment_id", NAMESPACE)
        assert app_spec.name == NAME
        assert app_spec.image == IMAGE

    @pytest.mark.parametrize("filename", (
            "invalid_no_health_check_defined_http",
            "invalid_no_health_check_defined_tcp",
            "invalid_ingress_port_number",
            "invalid_ingress_port_name",
    ))
    def test_invalid_configuration(self, load_app_config_testdata, factory, filename):
        with pytest.raises(InvalidConfiguration):
            factory(NAME, IMAGE, load_app_config_testdata(filename), "IO", "foo", "deployment_id", NAMESPACE)

    def test(self, load_app_config_testdata, factory, filename, attribute, value):
        app_spec = factory(NAME, IMAGE, load_app_config_testdata(filename), "IO", "foo", "deployment_id", NAMESPACE)
        assert app_spec is not None
        code = "app_spec.%s" % attribute
        actual = eval(code)
        assert isinstance(actual, _Lookup) is False  # _Lookup objects should not leak to AppSpec
        assert actual == value
