#!/usr/bin/env python
# -*- coding: utf-8

import pytest

from fiaas_deploy_daemon.specs.models import AppSpec, ResourceRequirementSpec, ResourcesSpec, PrometheusSpec, \
    PortSpec, CheckSpec, HttpCheckSpec, TcpCheckSpec, HealthCheckSpec, AutoscalerSpec, ExecCheckSpec, \
    LabelAndAnnotationSpec, IngressItemSpec, IngressPathMappingSpec

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
        resources=EMPTY_RESOURCE_SPEC,
        admin_access=False,
        secrets_in_environment=False,
        prometheus=PROMETHEUS_SPEC,
        ports=[
            PortSpec(protocol="http", name="http", port=80, target_port=8080),
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
        labels=LabelAndAnnotationSpec({}, {}, {}, {}),
        annotations=LabelAndAnnotationSpec({}, {}, {}, {}),
        ingresses=[IngressItemSpec(host=None, pathmappings=[IngressPathMappingSpec(path="/", port=80)])]
    )


@pytest.fixture
def app_spec_thrift(app_spec):
    return app_spec._replace(
        ports=[
            PortSpec(protocol="tcp", name="thrift", port=7999, target_port=7999),
        ],
        health_checks=HealthCheckSpec(
            liveness=CheckSpec(tcp=TcpCheckSpec(port=7999), http=None, execute=None, initial_delay_seconds=10,
                               period_seconds=10, success_threshold=1, timeout_seconds=1),
            readiness=CheckSpec(tcp=TcpCheckSpec(port=7999), http=None, execute=None,
                                initial_delay_seconds=10, period_seconds=10, success_threshold=1,
                                timeout_seconds=1)
        ),
        ingresses=[]
    )


@pytest.fixture
def app_spec_multiple_thrift_ports(app_spec_thrift):
    ports = [
        PortSpec(protocol="tcp", name="thrift1", port=7999, target_port=7999),
        PortSpec(protocol="tcp", name="thrift2", port=8000, target_port=8000),
    ]
    return app_spec_thrift._replace(ports=ports)


# TODO: remove this testcase, as this doesn't make sense after removing the host field in app_spec - config with host
# and no http ports will result in app_spec.ingresses == []
@pytest.fixture
def app_spec_thrift_with_host(app_spec_thrift):
    return app_spec_thrift


@pytest.fixture
def app_spec_thrift_and_http(app_spec):
    return app_spec._replace(
        ports=[
            PortSpec(protocol="http", name="http", port=80, target_port=8080),
            PortSpec(protocol="tcp", name="thrift", port=7999, target_port=7999),
        ],
        health_checks=HealthCheckSpec(
            liveness=CheckSpec(tcp=TcpCheckSpec(port=7999), http=None, execute=None, initial_delay_seconds=10,
                               period_seconds=10, success_threshold=1, timeout_seconds=1),
            readiness=CheckSpec(http=HttpCheckSpec(path="/", port=8080, http_headers={}), tcp=None, execute=None,
                                initial_delay_seconds=10, period_seconds=10, success_threshold=1,
                                timeout_seconds=1)),
    )


@pytest.fixture
def app_spec_teams_and_tags(app_spec):
    return app_spec._replace(
        ports=None,
        health_checks=None,
        teams=[u'Order Produkt Betaling'],
        tags=[u'høyt-i-stacken', u'ad-in', u'Anonnseinnlegging']
    )


@pytest.fixture
def app_spec_no_ports(app_spec):
    exec_check = CheckSpec(http=None, tcp=None, execute=ExecCheckSpec(command="/app/check.sh"),
                           initial_delay_seconds=10, period_seconds=10, success_threshold=1,
                           timeout_seconds=1)
    return app_spec._replace(ports=[],
                             health_checks=HealthCheckSpec(liveness=exec_check, readiness=exec_check),
                             ingresses=[])
