#!/usr/bin/env python
# -*- coding: utf-8
import mock
import pytest
from fiaas_deploy_daemon.deployer.kubernetes.ingress import IngressDeployer
from fiaas_deploy_daemon.config import Configuration

LABELS = {"ingress_deployer": "pass through"}
INGRESSES_URI = '/apis/extensions/v1beta1/namespaces/default/ingresses/'


class TestIngressDeployer(object):
    @pytest.fixture
    def deployer(self):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.infrastructure = "diy"
        config.environment = "test"
        config.ingress_suffixes = ["svc.test.finn.no", "127.0.0.1.xip.io"]
        return IngressDeployer(config)

    @pytest.mark.parametrize("host,expected", [
        ("www.finn.no", "www.finn.no"),
        ("m.finn.no", "m.finn.no"),
        ("kart.finn.no", "kart.finn.no"),
    ])
    def test_make_ingress_host_prod(self, app_spec, host, expected):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.infrastructure = "diy"
        config.environment = "prod"
        deployer = IngressDeployer(config)
        assert deployer._make_ingress_host(app_spec._replace(host=host)) == expected

    @pytest.mark.parametrize("host,expected", [
        ("www.finn.no", "test.finn.no"),
        ("m.finn.no", "test.m.finn.no"),
        ("kart.finn.no", "test.kart.finn.no"),
    ])
    def test_generate_hosts(self, app_spec, deployer, host, expected):
        hosts = list(deployer._generate_hosts(app_spec._replace(host=host)))
        assert hosts == [expected, "testapp.svc.test.finn.no", "testapp.127.0.0.1.xip.io"]

    def test_generate_hosts_no_host(self, app_spec, deployer):
        hosts = list(deployer._generate_hosts(app_spec._replace(host=None)))
        assert hosts == ["testapp.svc.test.finn.no", "testapp.127.0.0.1.xip.io"]

    @pytest.mark.parametrize("host,expected", [
        ("www.finn.no", "test.finn.no"),
        ("m.finn.no", "test.m.finn.no"),
        ("kart.finn.no", "test.kart.finn.no"),
    ])
    def test_deploy_new_ingress(self, host, expected, app_spec, post, deployer):
        deployer.deploy(app_spec._replace(host=host), LABELS)

        expected_ingress = {
            'spec': {
                'rules': [{
                    'host': expected,
                    'http': {'paths': [{
                        'path': '/',
                        'backend': {
                            'serviceName': 'testapp',
                            'servicePort': 80
                        }}]
                    }
                }, {
                    'host': "testapp.svc.test.finn.no",
                    'http': {'paths': [{
                        'path': '/',
                        'backend': {
                            'serviceName': 'testapp',
                            'servicePort': 80
                        }}]
                    }
                }, {
                    'host': "testapp.127.0.0.1.xip.io",
                    'http': {'paths': [{
                        'path': '/',
                        'backend': {
                            'serviceName': 'testapp',
                            'servicePort': 80
                        }}]
                    }
                }]
            },
            'metadata': pytest.helpers.create_metadata('testapp', labels=LABELS, external=True)
        }

        pytest.helpers.assert_any_call(post, INGRESSES_URI, expected_ingress)

    def test_deploy_new_ingress_no_host(self, app_spec, post, deployer):
        deployer.deploy(app_spec._replace(host=None), LABELS)

        expected_ingress = {
            'spec': {
                'rules': [{
                    'host': "testapp.svc.test.finn.no",
                    'http': {'paths': [{
                        'path': '/',
                        'backend': {
                            'serviceName': 'testapp',
                            'servicePort': 80
                        }}]
                    }
                }, {
                    'host': "testapp.127.0.0.1.xip.io",
                    'http': {'paths': [{
                        'path': '/',
                        'backend': {
                            'serviceName': 'testapp',
                            'servicePort': 80
                        }}]
                    }
                }]
            },
            'metadata': pytest.helpers.create_metadata('testapp', labels=LABELS, external=False)
        }

        pytest.helpers.assert_any_call(post, INGRESSES_URI, expected_ingress)

    def test_deploy_new_ingress_dev_gke(self, request, delete, get, post):
        app_spec = request.getfuncargvalue("app_spec")
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.infrastructure = "gke"
        config.environment = "dev"
        config.ingress_suffixes = ["svc.dev.finn.no", "k8s-gke.dev.finn.no"]
        deployer = IngressDeployer(config)
        deployer.deploy(app_spec, LABELS)

        expected_ingress = {
            'spec': {
                'rules': [{
                    'host': 'testapp.svc.dev.finn.no',
                    'http': {'paths': [{
                        'path': '/',
                        'backend': {
                            'serviceName': 'testapp',
                            'servicePort': 80
                        }}]
                    }
                }, {
                    'host': 'testapp.k8s-gke.dev.finn.no',
                    'http': {'paths': [{
                        'path': '/',
                        'backend': {
                            'serviceName': 'testapp',
                            'servicePort': 80
                        }}]
                    }
                }]
            },
            'metadata': pytest.helpers.create_metadata('testapp', labels=LABELS, external=False)
        }

        pytest.helpers.assert_any_call(post, INGRESSES_URI, expected_ingress)

    @pytest.mark.parametrize("spec_name", (
            "app_spec_thrift_with_host",
            "app_spec_thrift"
    ))
    def test_remove_existing_ingress_if_not_needed(self, request, delete, get, post, deployer, spec_name):
        app_spec = request.getfuncargvalue(spec_name)
        resp = mock.MagicMock()
        get.return_value = resp
        resp.json.return_value = {
            'spec': {
                'rules': [{
                    'host': 'test.finn.no',
                    'http': {'paths': [{
                        'path': '/',
                        'backend': {
                            'serviceName': 'testapp',
                            'servicePort': 80
                        }}]
                    }}, {
                    'host': 'test.k8s1-prod1.z01.finn.no',
                    'http': {'paths': [{
                        'path': '/',
                        'backend': {
                            'serviceName': 'testapp',
                            'servicePort': 80
                        }}]
                    }}
                ]
            },
            'metadata': pytest.helpers.create_metadata('testapp', labels=LABELS)
        }

        deployer.deploy(app_spec, LABELS)

        pytest.helpers.assert_no_calls(post, INGRESSES_URI)
        pytest.helpers.assert_any_call(delete, INGRESSES_URI + "testapp")
