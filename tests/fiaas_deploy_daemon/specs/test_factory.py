#!/usr/bin/env python
# -*- coding: utf-8
import os
import pytest
from requests import Session, HTTPError
from requests_file import FileAdapter

from fiaas_deploy_daemon.specs.factory import SpecFactory

IMAGE = u"finntech/docker-image:some-version"
NAME = u"application-name"


class TestFactory(object):
    @pytest.fixture()
    def session(self):
        session = Session()
        session.mount("file://", FileAdapter())
        return session

    @pytest.fixture()
    def factory(self, session):
        return SpecFactory(session)

    @staticmethod
    def _make_url(filename):
        test_dir = os.path.abspath(os.path.dirname(__file__))
        path = os.path.join(test_dir, "data", filename)
        return "file://{}.yml".format(path)

    def test_failed_request_raises_exception(self, factory):
        with pytest.raises(HTTPError):
            factory(NAME, IMAGE, self._make_url("non-existing-file"))

    @pytest.mark.parametrize("filename,value", [
        ("default_service", 2),
        ("full_config", 2),
        ("old_service", 2),
        ("replicas", 1)
    ])
    def test_replicas(self, factory, filename, value):
        app_spec = factory(NAME, IMAGE, self._make_url(filename))
        assert app_spec.replicas == value

    @pytest.mark.parametrize("filename,limit_cpu,limit_memory", [
        ("default_service", 1, 1),
        ("full_config", 1, 1),
        ("old_service", 1, 1),
        ("resource_limit_cpu", "500m", 1),
        ("resource_limit_cpu_and_memory", "500m", "1024m"),
        ("resource_limit_memory", 1, "1024m"),
        ("resource_just_limit", "500m", "1024m"),
        ("resource_request_cpu", 1, 1),
        ("resource_request_cpu_and_memory", 1, 1),
        ("resource_request_memory", 1, 1),
        ("resource_just_request", None, None)
    ])
    def test_resource_limit(self, factory, filename, limit_cpu, limit_memory):
        app_spec = factory(NAME, IMAGE, self._make_url(filename))
        assert app_spec.resources.limits.cpu == limit_cpu
        assert app_spec.resources.limits.memory == limit_memory

    @pytest.mark.parametrize("filename,request_cpu,request_memory", [
        ("default_service", 2, 2),
        ("full_config", 2, 2),
        ("old_service", 2, 2),
        ("resource_limit_cpu", 2, 2),
        ("resource_limit_cpu_and_memory", 2, 2),
        ("resource_just_limit", None, None),
        ("resource_limit_memory", 2, 2),
        ("resource_request_cpu", "500m", 2),
        ("resource_request_cpu_and_memory", "500m", "1024m"),
        ("resource_just_request", "500m", "1024m"),
        ("resource_request_memory", 2, "1024m")
    ])
    def test_resource_request(self, factory, filename, request_cpu, request_memory):
        app_spec = factory(NAME, IMAGE, self._make_url(filename))
        assert app_spec.resources.requests.cpu == request_cpu
        assert app_spec.resources.requests.memory == request_memory

    @pytest.mark.parametrize("filename,exposed_port,service_port", [
        ("default_service", 80, 80),
        ("full_config", 5000, 8080),
        ("old_service", 5000, 8080),
        ("service_exposed_port", 5000, 80),
        ("service_service_port", 80, 8080),
    ])
    def test_service_ports(self, factory, filename, exposed_port, service_port):
        app_spec = factory(NAME, IMAGE, self._make_url(filename))
        service_spec = app_spec.services[0]
        assert service_spec.exposed_port == exposed_port
        assert service_spec.service_port == service_port

    @pytest.mark.parametrize("filename,ingress,readiness,liveness", [
        ("default_service", u"/", u"/", u"/"),
        ("full_config", u"/ingress", u"/ingress/smoketest", u"/ingress/health"),
        ("old_service", u"/ingress", u"/ingress/smoketest", u"/ingress/health"),
        ("service_ingress", u"/ingress", u"/", u"/"),
        ("service_readiness", u"/", u"/smoketest", u"/"),
        ("service_liveness", u"/", u"/", u"/health"),
    ])
    def test_service_paths(self, factory, filename, ingress, readiness, liveness):
        app_spec = factory(NAME, IMAGE, self._make_url(filename))
        service_spec = app_spec.services[0]
        assert service_spec.ingress == ingress
        assert service_spec.readiness.path == readiness
        assert service_spec.liveness.path == liveness

    @pytest.mark.parametrize("filename,typ,probe_delay", [
        ("default_service", u"http", 10),
        ("full_config", u"https", 100),
        ("old_service", u"https", 100),
    ])
    def test_service_fields(self, factory, filename, typ, probe_delay):
        app_spec = factory(NAME, IMAGE, self._make_url(filename))
        service_spec = app_spec.services[0]
        assert service_spec.type == typ
        assert service_spec.probe_delay == probe_delay

    @pytest.mark.parametrize("filename,protocols", [
        ("default_service", [u"http"]),
        ("full_config", [u"https"]),
        ("old_service", [u"https"]),
        ("thrift_http_service", [u"thrift", u"http"]),
    ])
    def test_multi_service_proto(self, factory, filename, protocols):
        app_spec = factory(NAME, IMAGE, self._make_url(filename))
        for i, service_spec in enumerate(app_spec.services):
            protocol = protocols[i]
            assert service_spec.type == protocol

    @pytest.mark.parametrize("filename,ports", [
        ("default_service", [80]),
        ("full_config", [8080]),
        ("old_service", [8080]),
        ("thrift_http_service", [7755, 9779]),
    ])
    def test_multi_service_service_port(self, factory, filename, ports):
        app_spec = factory(NAME, IMAGE, self._make_url(filename))
        for i, service_spec in enumerate(app_spec.services):
            port = ports[i]
            assert service_spec.service_port == port

    @pytest.mark.parametrize("filename,ports", [
        ("default_service", [80]),
        ("full_config", [5000]),
        ("old_service", [5000]),
        ("thrift_http_service", [7755, 9779]),
    ])
    def test_multi_service_exposed_port(self, factory, filename, ports):
        app_spec = factory(NAME, IMAGE, self._make_url(filename))
        for i, service_spec in enumerate(app_spec.services):
            port = ports[i]
            assert service_spec.exposed_port == port

    @pytest.mark.parametrize("filename,admin_access", [
        ("default_service", None),
        ("admin_access", "read-write")
    ])
    def test_admin_access(self, factory, filename, admin_access):
        app_spec = factory(NAME, IMAGE, self._make_url(filename))
        assert app_spec.admin_access == admin_access

    @pytest.mark.parametrize("filename,has_secrets", [
        ("default_service", False),
        ("has_secrets", True)
    ])
    def test_has_secrets(self, factory, filename, has_secrets):
        app_spec = factory(NAME, IMAGE, self._make_url(filename))
        assert app_spec.has_secrets == has_secrets

    @pytest.mark.parametrize("filename,namespace", [
        ("default_service", False),
    ])
    def test_no_namespace(self, factory, filename, namespace):
        app_spec = factory(NAME, IMAGE, self._make_url(filename))
        assert app_spec.namespace == "default"
