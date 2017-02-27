#!/usr/bin/env python
# -*- coding: utf-8

import pytest

from fiaas_deploy_daemon.specs.models import AppSpec, ResourceRequirementSpec, ResourcesSpec, PrometheusSpec, \
    PortSpec, CheckSpec, HttpCheckSpec, TcpCheckSpec, HealthCheckSpec, ConfigMapSpec

PROMETHEUS_SPEC = PrometheusSpec(enabled=True, port=8080, path='/internal-backstage/prometheus')
EMPTY_RESOURCE_SPEC = ResourcesSpec(requests=ResourceRequirementSpec(cpu=None, memory=None),
                                    limits=ResourceRequirementSpec(cpu=None, memory=None))
EMPTY_CONFIG_MAP_SPEC = ConfigMapSpec(volume=False, envs=[])


@pytest.fixture
def app_spec():
    return AppSpec(
        name="testapp",
        namespace="default",
        image="finntech/testimage:version",
        replicas=3,
        host=None,
        resources=EMPTY_RESOURCE_SPEC,
        admin_access=False,
        has_secrets=False,
        prometheus=PROMETHEUS_SPEC,
        ports=[
            PortSpec(protocol="http", name="http", port=80, target_port=8080, path="/"),
        ],
        health_checks=HealthCheckSpec(
            liveness=CheckSpec(tcp=TcpCheckSpec(port=8080), http=None, execute=None, initial_delay_seconds=10,
                               period_seconds=10, success_threshold=1, timeout_seconds=1),
            readiness=CheckSpec(http=HttpCheckSpec(path="/", port=8080, http_headers={}), tcp=None, execute=None,
                                initial_delay_seconds=10, period_seconds=10, success_threshold=1,
                                timeout_seconds=1)),
        teams=[u'foo'],
        tags=[u'bar'],
        config=EMPTY_CONFIG_MAP_SPEC
    )


@pytest.fixture
def app_spec_with_host(app_spec):
    return app_spec._replace(host="www.example.com")


@pytest.fixture
def app_spec_with_admin_access(app_spec):
    return app_spec._replace(admin_access=True)


@pytest.fixture
def app_spec_thrift():
    return AppSpec(
        admin_access=False,
        name="testapp",
        replicas=3,
        image="finntech/testimage:version",
        namespace="default",
        has_secrets=False,
        host=None,
        resources=EMPTY_RESOURCE_SPEC,
        prometheus=PROMETHEUS_SPEC,
        ports=[
            PortSpec(protocol="tcp", name="thrift", port=7999, target_port=7999, path=None),
        ],
        health_checks=HealthCheckSpec(
            liveness=CheckSpec(tcp=TcpCheckSpec(port=7999), http=None, execute=None, initial_delay_seconds=10,
                               period_seconds=10, success_threshold=1, timeout_seconds=1),
            readiness=CheckSpec(tcp=TcpCheckSpec(port=7999), http=None, execute=None,
                                initial_delay_seconds=10, period_seconds=10, success_threshold=1,
                                timeout_seconds=1)
        ),
        teams=[u'foo'],
        tags=[u'bar'],
        config=EMPTY_CONFIG_MAP_SPEC
    )


@pytest.fixture
def app_spec_thrift_with_host(app_spec_thrift):
    return app_spec_thrift._replace(host="www.example.com")


@pytest.fixture
def app_spec_thrift_and_http():
    return AppSpec(
        admin_access=False,
        name="testapp",
        replicas=3,
        image="finntech/testimage:version",
        namespace="default",
        has_secrets=False,
        host=None,
        resources=EMPTY_RESOURCE_SPEC,
        prometheus=PROMETHEUS_SPEC,
        ports=[
            PortSpec(protocol="http", name="http", port=80, target_port=8080, path="/"),
            PortSpec(protocol="tcp", name="thrift", port=7999, target_port=7999, path=None),
        ],
        health_checks=HealthCheckSpec(
            liveness=CheckSpec(tcp=TcpCheckSpec(port=7999), http=None, execute=None, initial_delay_seconds=10,
                               period_seconds=10, success_threshold=1, timeout_seconds=1),
            readiness=CheckSpec(http=HttpCheckSpec(path="/", port=8080, http_headers={}), tcp=None, execute=None,
                                initial_delay_seconds=10, period_seconds=10, success_threshold=1,
                                timeout_seconds=1)),
        teams=[u'foo'],
        tags=[u'bar'],
        config=EMPTY_CONFIG_MAP_SPEC
    )


@pytest.fixture
def app_spec_teams_and_tags():
    return AppSpec(
        admin_access=False,
        name="testapp",
        replicas=3,
        image="finntech/testimage:version",
        namespace="default",
        has_secrets=False,
        host=None,
        resources=EMPTY_RESOURCE_SPEC,
        prometheus=PROMETHEUS_SPEC,
        ports=None,
        health_checks=None,
        teams=[u'Order Produkt Betaling'],
        tags=[u'høyt-i-stacken', u'ad-in', u'Anonnseinnlegging'],
        config=EMPTY_CONFIG_MAP_SPEC
    )
