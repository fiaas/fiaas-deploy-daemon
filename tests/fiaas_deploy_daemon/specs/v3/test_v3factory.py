#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import, unicode_literals

import pytest

from fiaas_deploy_daemon.specs.v3.factory import Factory
from fiaas_deploy_daemon.specs.factory import SpecFactory, InvalidConfiguration

IMAGE = "finntech/docker-image:some-version"
NAME = "application-name"

TEST_DATA = {
    # v2minimal should test "all" possible default values
    "v3minimal": {
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
        "annotations.deployment": {},
        "annotations.horizontal_pod_autoscaler": {},
        "annotations.service": {},
        "annotations.ingress": {},
        "ingresses[0].host": None,
        "ingresses[0].pathmappings[0].path": "/",
        "ingresses[0].pathmappings[0].port": 80,
        "secrets_in_environment": False,
        "admin_access": False,
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
        return SpecFactory(Factory(), {})

    @pytest.mark.parametrize("filename", (
            "v3minimal",
    ))
    def test_name_and_image(self, load_app_config_testdata, factory, filename):
        app_spec = factory(NAME, IMAGE, load_app_config_testdata(filename), "IO", "foo", "deployment_id")
        assert app_spec.name == NAME
        assert app_spec.image == IMAGE

    @pytest.mark.parametrize("filename", (
            "no_health_check_defined_http",
            "no_health_check_defined_tcp",
    ))
    def test_no_health_check(self, load_app_config_testdata, factory, filename):
        with pytest.raises(InvalidConfiguration):
            factory(NAME, IMAGE, load_app_config_testdata(filename), "IO", "foo", "deployment_id")

    def test(self, load_app_config_testdata, factory, filename, attribute, value):
        app_spec = factory(NAME, IMAGE, load_app_config_testdata(filename), "IO", "foo", "deployment_id")
        assert app_spec is not None
        code = "app_spec.%s" % attribute
        actual = eval(code)
        assert actual == value
