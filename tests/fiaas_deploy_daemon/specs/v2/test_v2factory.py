#!/usr/bin/env python
# -*- coding: utf-8

import pytest

from fiaas_deploy_daemon.specs.v2.factory import Factory
from fiaas_deploy_daemon.specs.factory import SpecFactory
from fiaas_deploy_daemon.specs import InvalidConfiguration

IMAGE = u"finntech/docker-image:some-version"
NAME = u"application-name"

TEST_DATA = {
    # v2minimal should test "all" possible default values
    u"v2minimal": {
        u"namespace": u"default",
        u"replicas": 2,
        u"autoscaler.enabled": False,
        u"autoscaler.min_replicas": 2,
        u"autoscaler.cpu_threshold_percentage": 50,
        u"host": None,
        u"admin_access": False,
        u"has_secrets": False,
        u"prometheus.enabled": True,
        u"prometheus.port": u"http",
        u"prometheus.path": u"/internal-backstage/prometheus",
        u"resources.limits.memory": None,
        u"resources.limits.cpu": None,
        u"resources.requests.memory": None,
        u"resources.requests.cpu": None,
        u"ports[0].protocol": u"http",
        u"ports[0].name": u"http",
        u"ports[0].port": 80,
        u"ports[0].target_port": 80,
        u"ports[0].path": u"/",
        u"health_checks.liveness.http.path": u"/",
        u"health_checks.liveness.http.port": u"http",
        u"health_checks.liveness.http.http_headers": {},
        u"health_checks.liveness.initial_delay_seconds": 10,
        u"health_checks.liveness.period_seconds": 10,
        u"health_checks.liveness.success_threshold": 1,
        u"health_checks.liveness.timeout_seconds": 1,
        u"health_checks.liveness.execute": None,
        u"health_checks.liveness.tcp": None,
        u"health_checks.readiness.http.path": u"/",
        u"health_checks.readiness.http.port": u"http",
        u"health_checks.readiness.http.http_headers": {},
        u"health_checks.readiness.initial_delay_seconds": 10,
        u"health_checks.readiness.period_seconds": 10,
        u"health_checks.readiness.success_threshold": 1,
        u"health_checks.readiness.timeout_seconds": 1,
        u"health_checks.readiness.execute": None,
        u"health_checks.readiness.tcp": None,
        u"config.envs": [],
        u"config.volume": False
    },
    # full_config should test overriding "all" possible values
    u"full_config": {
        u"namespace": u"test",
        u"replicas": 20,
        u"autoscaler.enabled": True,
        u"autoscaler.min_replicas": 3,
        u"autoscaler.cpu_threshold_percentage": 60,
        u"host": u"some.host.no",
        u"admin_access": True,
        u"has_secrets": True,
        u"prometheus.enabled": True,
        u"prometheus.port": u"prom_port",
        u"prometheus.path": u"/prometheus",
        u"resources.limits.memory": u"128Mi",
        u"resources.limits.cpu": u"100m",
        u"resources.requests.memory": u"64Mi",
        u"resources.requests.cpu": u"50m",
        u"ports[0].protocol": u"http",
        u"ports[0].name": u"prom_port",
        u"ports[0].port": 8080,
        u"ports[0].target_port": 5000,
        u"ports[0].path": u"/",
        u"health_checks.liveness.http.path": u"/liveness",
        u"health_checks.liveness.http.port": 1111,
        u"health_checks.liveness.http.http_headers": {u"key": u"value"},
        u"health_checks.liveness.initial_delay_seconds": 100,
        u"health_checks.liveness.period_seconds": 100,
        u"health_checks.liveness.success_threshold": 10,
        u"health_checks.liveness.timeout_seconds": 10,
        u"health_checks.liveness.execute": None,
        u"health_checks.liveness.tcp": None,
        u"health_checks.readiness.http.path": u"/readiness",
        u"health_checks.readiness.http.port": 2222,
        u"health_checks.readiness.http.http_headers": {u"key2": u"value2"},
        u"health_checks.readiness.initial_delay_seconds": 20,
        u"health_checks.readiness.period_seconds": 20,
        u"health_checks.readiness.success_threshold": 2,
        u"health_checks.readiness.timeout_seconds": 2,
        u"health_checks.readiness.execute": None,
        u"health_checks.readiness.tcp": None,
        u"config.envs[0]": u"FIRST_ENV",
        u"config.envs[1]": u"SECOND_ENV",
        u"config.volume": True
    },
    u"exec_config": {
        u"health_checks.liveness.execute.command": u"liveness",
        u"health_checks.liveness.tcp": None,
        u"health_checks.liveness.http": None,
        u"health_checks.readiness.execute.command": u"readiness",
        u"health_checks.readiness.tcp": None,
        u"health_checks.readiness.http": None,
    },
    u"tcp_config": {
        u"health_checks.liveness.tcp.port": 1111,
        u"health_checks.liveness.execute": None,
        u"health_checks.liveness.http": None,
        u"health_checks.readiness.tcp.port": 2222,
        u"health_checks.readiness.execute": None,
        u"health_checks.readiness.http": None,
    },
    u"multiple_ports": {
        u"ports[0].protocol": u"http",
        u"ports[0].name": u"main_port",
        u"ports[0].port": 8080,
        u"ports[0].target_port": 5000,
        u"ports[0].path": u"/",
        u"ports[1].protocol": u"http",
        u"ports[1].name": u"prom_port",
        u"ports[1].port": 8081,
        u"ports[1].target_port": 5001,
        u"ports[1].path": u"/prometheus",
        u"ports[2].protocol": u"tcp",
        u"ports[2].name": u"thrift_port",
        u"ports[2].port": 7000,
        u"ports[2].target_port": 7000,
    },
    u"default_health_check": {
        u"ports[0].protocol": u"http",
        u"ports[0].name": u"main_port",
        u"ports[0].port": 8080,
        u"health_checks.liveness.http.path": u"/",
        u"health_checks.liveness.http.port": u"main_port",
        u"health_checks.liveness.execute": None,
        u"health_checks.liveness.tcp": None,
        u"health_checks.readiness.http.path": u"/",
        u"health_checks.readiness.http.port": u"main_port",
        u"health_checks.readiness.execute": None,
        u"health_checks.readiness.tcp": None,
    },
    u"host": {
        u"host": u"some.host.no",
    },
    u"only_liveness": {
        u"health_checks.liveness.http.path": u"/liveness",
        u"health_checks.liveness.http.port": 1111,
        u"health_checks.liveness.http.http_headers": {u"key": u"value"},
        u"health_checks.liveness.initial_delay_seconds": 100,
        u"health_checks.liveness.period_seconds": 100,
        u"health_checks.liveness.success_threshold": 10,
        u"health_checks.liveness.timeout_seconds": 10,
        u"health_checks.liveness.execute": None,
        u"health_checks.liveness.tcp": None,
        u"health_checks.readiness.http.path": u"/liveness",
        u"health_checks.readiness.http.port": 1111,
        u"health_checks.readiness.http.http_headers": {u"key": u"value"},
        u"health_checks.readiness.initial_delay_seconds": 100,
        u"health_checks.readiness.period_seconds": 100,
        u"health_checks.readiness.success_threshold": 10,
        u"health_checks.readiness.timeout_seconds": 10,
        u"health_checks.readiness.execute": None,
        u"health_checks.readiness.tcp": None,
    },
    u"config_as_env": {
        u"config.envs[0]": u"FIRST_ENV",
        u"config.envs[1]": u"SECOND_ENV",
        u"config.volume": False
    },
    u"config_as_volume": {
        u"config.envs": [],
        u"config.volume": True
    }
}


def pytest_generate_tests(metafunc):
    fixtures = ("filename", "attribute", "value")
    if metafunc.cls == TestFactory and all(fixname in metafunc.fixturenames for fixname in fixtures):
        for filename in TEST_DATA:
            for attribute in TEST_DATA[filename]:
                value = TEST_DATA[filename][attribute]
                fixture_args = {"filename": filename, "attribute": attribute, "value": value}
                metafunc.addcall(fixture_args, "{}/{}=={}".format(filename, attribute.replace(".", "_"), repr(value).replace(".", "_")))


class TestFactory(object):
    @pytest.fixture
    def factory(self):
        return SpecFactory({2: Factory()})

    @pytest.mark.parametrize("filename", (
            "v2minimal",
            "full_config"
    ))
    def test_name_and_image(self, load_app_config_testdata, factory, filename):
        app_spec = factory(NAME, IMAGE, load_app_config_testdata(filename), "IO", "foo")
        assert app_spec.name == NAME
        assert app_spec.image == IMAGE

    def test_no_health_check(self, load_app_config_testdata, factory):
        with pytest.raises(InvalidConfiguration):
            factory(NAME, IMAGE, load_app_config_testdata("no_health_check_defined"), "IO", "foo")

    def test(self, load_app_config_testdata, factory, filename, attribute, value):
        app_spec = factory(NAME, IMAGE, load_app_config_testdata(filename), "IO", "foo")
        assert app_spec is not None
        code = "app_spec.%s" % attribute
        actual = eval(code)
        assert actual == value
