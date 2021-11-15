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
import mock
import pytest
from k8s import config
from k8s.client import NotFound

from fiaas_deploy_daemon.specs.models import AppSpec, \
    ResourceRequirementSpec, ResourcesSpec, PrometheusSpec, DatadogSpec, \
    PortSpec, CheckSpec, HttpCheckSpec, TcpCheckSpec, HealthCheckSpec, \
    AutoscalerSpec, ExecCheckSpec, LabelAndAnnotationSpec, \
    IngressItemSpec, IngressPathMappingSpec, StrongboxSpec, IngressTlsSpec

PROMETHEUS_SPEC = PrometheusSpec(enabled=True, port='http', path='/internal-backstage/prometheus')
DATADOG_SPEC = DatadogSpec(enabled=False, tags={})
AUTOSCALER_SPEC = AutoscalerSpec(enabled=False, min_replicas=2, max_replicas=3, cpu_threshold_percentage=50)
EMPTY_RESOURCE_SPEC = ResourcesSpec(requests=ResourceRequirementSpec(cpu=None, memory=None),
                                    limits=ResourceRequirementSpec(cpu=None, memory=None))


# App specs

@pytest.fixture
def app_spec():
    return AppSpec(
        uid="c1f34517-6f54-11ea-8eaf-0ad3d9992c8c",
        name="testapp",
        namespace="default",
        image="finntech/testimage:version",
        autoscaler=AUTOSCALER_SPEC,
        resources=EMPTY_RESOURCE_SPEC,
        admin_access=False,
        secrets_in_environment=False,
        prometheus=PROMETHEUS_SPEC,
        datadog=DATADOG_SPEC,
        ports=[
            PortSpec(protocol="http", name="http", port=80, target_port=8080),
        ],
        health_checks=HealthCheckSpec(
            liveness=CheckSpec(tcp=TcpCheckSpec(port=8080), http=None, execute=None, initial_delay_seconds=10,
                               period_seconds=10, success_threshold=1, failure_threshold=3, timeout_seconds=1),
            readiness=CheckSpec(http=HttpCheckSpec(path="/", port=8080, http_headers={}), tcp=None, execute=None,
                                initial_delay_seconds=10, period_seconds=10, success_threshold=1, failure_threshold=3,
                                timeout_seconds=1)),
        teams=[u'foo'],
        tags=[u'bar'],
        deployment_id="test_app_deployment_id",
        labels=LabelAndAnnotationSpec({}, {}, {}, {}, {}, {}, {}),
        annotations=LabelAndAnnotationSpec({}, {}, {}, {}, {}, {}, {}),
        ingresses=[IngressItemSpec(host=None, pathmappings=[IngressPathMappingSpec(path="/", port=80)], annotations={})],
        strongbox=StrongboxSpec(enabled=False, iam_role=None, aws_region="eu-west-1", groups=None),
        singleton=False,
        ingress_tls=IngressTlsSpec(enabled=False, certificate_issuer=None),
        secrets=[],
        app_config={}
    )


@pytest.fixture
def app_spec_thrift(app_spec):
    return app_spec._replace(
        ports=[
            PortSpec(protocol="tcp", name="thrift", port=7999, target_port=7999),
        ],
        health_checks=HealthCheckSpec(
            liveness=CheckSpec(tcp=TcpCheckSpec(port=7999), http=None, execute=None, initial_delay_seconds=10,
                               period_seconds=10, success_threshold=1, failure_threshold=3, timeout_seconds=1),
            readiness=CheckSpec(tcp=TcpCheckSpec(port=7999), http=None, execute=None,
                                initial_delay_seconds=10, period_seconds=10, success_threshold=1, failure_threshold=3,
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


@pytest.fixture
def app_spec_thrift_and_http(app_spec):
    return app_spec._replace(
        ports=[
            PortSpec(protocol="http", name="http", port=80, target_port=8080),
            PortSpec(protocol="tcp", name="thrift", port=7999, target_port=7999),
        ],
        health_checks=HealthCheckSpec(
            liveness=CheckSpec(tcp=TcpCheckSpec(port=7999), http=None, execute=None, initial_delay_seconds=10,
                               period_seconds=10, success_threshold=1, failure_threshold=3, timeout_seconds=1),
            readiness=CheckSpec(http=HttpCheckSpec(path="/", port=8080, http_headers={}), tcp=None, execute=None,
                                initial_delay_seconds=10, period_seconds=10, success_threshold=1, failure_threshold=3,
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
                           initial_delay_seconds=10, period_seconds=10, success_threshold=1, failure_threshold=3,
                           timeout_seconds=1)
    return app_spec._replace(ports=[],
                             health_checks=HealthCheckSpec(liveness=exec_check, readiness=exec_check),
                             ingresses=[])


# k8s client library mocks


@pytest.fixture(autouse=True)
def k8s_config(monkeypatch):
    """Configure k8s for test-runs"""
    monkeypatch.setattr(config, "api_server", "https://10.0.0.1")
    monkeypatch.setattr(config, "api_token", "password")
    monkeypatch.setattr(config, "verify_ssl", False)


@pytest.fixture()
def get():
    with mock.patch('k8s.client.Client.get') as mockk:
        mockk.side_effect = NotFound()
        yield mockk


@pytest.fixture()
def post():
    with mock.patch('k8s.client.Client.post') as mockk:
        yield mockk


@pytest.fixture()
def put():
    with mock.patch('k8s.client.Client.put') as mockk:
        yield mockk


@pytest.fixture()
def delete():
    with mock.patch('k8s.client.Client.delete') as mockk:
        yield mockk


@pytest.fixture(scope="session", autouse=True)
def _open():
    """
    mock open() to return predefined namespace if the file we're trying to read is
    /var/run/secrets/kubernetes.io/serviceaccount/namespace. Otherwise, pass all parameters to the real open() builtin
    and call it
    """
    real_open = open

    def _mock_namespace_file_open(name, *args, **kwargs):
        namespace = "namespace-from-file"
        if name == "/var/run/secrets/kubernetes.io/serviceaccount/namespace":
            return mock.mock_open(read_data=namespace)()
        else:
            return real_open(name, *args, **kwargs)

    with mock.patch("__builtin__.open") as mock_open:
        mock_open.side_effect = _mock_namespace_file_open
        yield mock_open


@pytest.fixture(scope="session", params=(
    "v1.9.11",
    "v1.12.10",
    "v1.14.10",
    "v1.16.13",
    "v1.18.6",
    pytest.param("v1.19.4", marks=pytest.mark.e2e_latest)
))
def k8s_version(request):
    yield request.param
