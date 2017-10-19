#!/usr/bin/env python
# -*- coding: utf-8

import pytest

from fiaas_deploy_daemon.specs.models import AppSpec, ResourceRequirementSpec, ResourcesSpec, PrometheusSpec, \
    PortSpec, CheckSpec, HttpCheckSpec, TcpCheckSpec, HealthCheckSpec, AutoscalerSpec

PROMETHEUS_SPEC = PrometheusSpec(enabled=True, port='http', path='/internal-backstage/prometheus')
AUTOSCALER_SPEC = AutoscalerSpec(enabled=False, min_replicas=2, cpu_threshold_percentage=50)
EMPTY_RESOURCE_SPEC = ResourcesSpec(requests=ResourceRequirementSpec(cpu=None, memory=None),
                                    limits=ResourceRequirementSpec(cpu=None, memory=None))


@pytest.fixture
def app_spec():
    return AppSpec(
        name="testapp",
        namespace="default",
        image="finntech/testimage:version",
        replicas=3,
        autoscaler=AUTOSCALER_SPEC,
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
        deployment_id="test_app_deployment_id",
        labels={},
        annotations={}
    )


@pytest.fixture
def app_spec_thrift(app_spec):
    return app_spec._replace(
        ports=[
            PortSpec(protocol="tcp", name="thrift", port=7999, target_port=7999, path=None),
        ],
        health_checks=HealthCheckSpec(
            liveness=CheckSpec(tcp=TcpCheckSpec(port=7999), http=None, execute=None, initial_delay_seconds=10,
                               period_seconds=10, success_threshold=1, timeout_seconds=1),
            readiness=CheckSpec(tcp=TcpCheckSpec(port=7999), http=None, execute=None,
                                initial_delay_seconds=10, period_seconds=10, success_threshold=1,
                                timeout_seconds=1)
        )
    )


@pytest.fixture
def app_spec_multiple_thrift_ports(app_spec_thrift):
    ports = [
        PortSpec(protocol="tcp", name="thrift1", port=7999, target_port=7999, path=None),
        PortSpec(protocol="tcp", name="thrift2", port=8000, target_port=8000, path=None),
    ]
    return app_spec_thrift._replace(ports=ports)


@pytest.fixture
def app_spec_thrift_with_host(app_spec_thrift):
    return app_spec_thrift._replace(host="www.example.com")


@pytest.fixture
def app_spec_thrift_and_http(app_spec):
    return app_spec._replace(
        ports=[
            PortSpec(protocol="http", name="http", port=80, target_port=8080, path="/"),
            PortSpec(protocol="tcp", name="thrift", port=7999, target_port=7999, path=None),
        ],
        health_checks=HealthCheckSpec(
            liveness=CheckSpec(tcp=TcpCheckSpec(port=7999), http=None, execute=None, initial_delay_seconds=10,
                               period_seconds=10, success_threshold=1, timeout_seconds=1),
            readiness=CheckSpec(http=HttpCheckSpec(path="/", port=8080, http_headers={}), tcp=None, execute=None,
                                initial_delay_seconds=10, period_seconds=10, success_threshold=1,
                                timeout_seconds=1))
    )


@pytest.fixture
def app_spec_teams_and_tags(app_spec):
    return app_spec._replace(
        ports=None,
        health_checks=None,
        teams=[u'Order Produkt Betaling'],
        tags=[u'høyt-i-stacken', u'ad-in', u'Anonnseinnlegging']
    )
