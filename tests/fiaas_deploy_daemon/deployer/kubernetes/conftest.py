#!/usr/bin/env python
# -*- coding: utf-8

import mock
import pytest

from fiaas_deploy_daemon.specs.models import AppSpec, ResourceRequirementSpec, ResourcesSpec, PrometheusSpec, \
    PortSpec, CheckSpec, HttpCheckSpec, TcpCheckSpec, HealthCheckSpec
from k8s.client import NotFound

PROMETHEUS_SPEC = PrometheusSpec(enabled=True, port=8080, path='/internal-backstage/prometheus')
EMPTY_RESOURCE_SPEC = ResourcesSpec(requests=ResourceRequirementSpec(cpu=None, memory=None),
                                    limits=ResourceRequirementSpec(cpu=None, memory=None))


@pytest.fixture(autouse=True)
def get():
    with mock.patch("k8s.client.Client.get") as m:
        m.side_effect = NotFound()
        yield m


@pytest.fixture(autouse=True)
def post():
    with mock.patch("k8s.client.Client.post") as m:
        yield m


@pytest.fixture(autouse=True)
def delete():
    with mock.patch("k8s.client.Client.delete") as m:
        yield m


@pytest.fixture
def app_spec():
    return AppSpec(
        name="testapp",
        namespace="default",
        image="finntech/testimage:version",
        replicas=3,
        host=None,
        resources=EMPTY_RESOURCE_SPEC,
        admin_access=None,
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
                                timeout_seconds=1)
        )
    )


@pytest.fixture
def app_spec_with_host(app_spec):
    return app_spec._replace(host="www.finn.no")


@pytest.fixture
def app_spec_thrift():
    return AppSpec(
        admin_access=None,
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
        ))


@pytest.fixture
def app_spec_thrift_with_host(app_spec_thrift):
    return app_spec_thrift._replace(host="www.finn.no")


@pytest.fixture
def app_spec_thrift_and_http():
    return AppSpec(
        admin_access=None,
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
                                timeout_seconds=1)
        ))


@pytest.helpers.register
def create_metadata(app_name, namespace='default', prometheus=False, labels=None, external=None):
    if not labels:
        labels = {
            'app': app_name,
            'fiaas/version': 'version',
            'fiaas/deployed_by': '1'
        }
    metadata = {
        'labels': labels,
        'namespace': namespace,
        'name': app_name,
    }
    if external is not None:
        metadata['annotations'] = {
            'fiaas/expose': str(external).lower()
        }
    if prometheus:
        prom_annotations = {
            'prometheus.io/port': '8080',
            'prometheus.io/path': '/internal-backstage/prometheus',
            'prometheus.io/scrape': 'true'
        }
        if 'annotations' in metadata:
            metadata['annotations'].update(prom_annotations)
        else:
            metadata['annotations'] = prom_annotations
    return metadata
