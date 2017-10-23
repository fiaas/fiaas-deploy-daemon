#!/usr/bin/env python
# -*- coding: utf-8
import mock
import pytest
from fiaas_deploy_daemon.deployer.kubernetes.ingress import IngressDeployer
from fiaas_deploy_daemon.config import Configuration, HostRewriteRule

LABELS = {"ingress_deployer": "pass through"}
INGRESSES_URI = '/apis/extensions/v1beta1/namespaces/default/ingresses/'


class TestIngressDeployer(object):
    @pytest.fixture
    def deployer(self):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.infrastructure = "diy"
        config.environment = "test"
        config.ingress_suffixes = ["svc.test.example.com", "127.0.0.1.xip.io"]
        config.host_rewrite_rules = [
            HostRewriteRule("www.example.com=test.example.com"),
            HostRewriteRule(r"([a-z0-9](?:[-a-z0-9]*[a-z0-9])?).example.com=test.\1.example.com")]
        return IngressDeployer(config)

    @pytest.mark.parametrize("host,expected", [
        ("www.example.com", "www.example.com"),
        ("m.example.com", "m.example.com"),
        ("kart.example.com", "kart.example.com"),
    ])
    def test_make_ingress_host_prod(self, app_spec, host, expected):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.infrastructure = "diy"
        config.environment = "prod"
        deployer = IngressDeployer(config)
        assert deployer._make_ingress_host(app_spec._replace(host=host)) == expected

    @pytest.mark.parametrize("host,expected", [
        ("www.example.com", "test.example.com"),
        ("m.example.com", "test.m.example.com"),
        ("kart.example.com", "test.kart.example.com"),
    ])
    def test_generate_hosts(self, app_spec, deployer, host, expected):
        hosts = list(deployer._generate_hosts(app_spec._replace(host=host)))
        assert hosts == [expected, "testapp.svc.test.example.com", "testapp.127.0.0.1.xip.io"]

    def test_generate_hosts_no_host(self, app_spec, deployer):
        hosts = list(deployer._generate_hosts(app_spec._replace(host=None)))
        assert hosts == ["testapp.svc.test.example.com", "testapp.127.0.0.1.xip.io"]

    @pytest.mark.parametrize("host,expected", [
        ("www.example.com", "test.example.com"),
        ("m.example.com", "test.m.example.com"),
        ("kart.example.com", "test.kart.example.com"),
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
                    'host': "testapp.svc.test.example.com",
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
                }],
                'tls': [],
            },
            'metadata': pytest.helpers.create_metadata('testapp', labels=LABELS, external=True)
        }

        pytest.helpers.assert_any_call(post, INGRESSES_URI, expected_ingress)

    def test_deploy_new_ingress_no_host(self, app_spec, post, deployer):
        deployer.deploy(app_spec._replace(host=None), LABELS)

        expected_ingress = {
            'spec': {
                'rules': [{
                    'host': "testapp.svc.test.example.com",
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
                }],
                'tls': [],
            },
            'metadata': pytest.helpers.create_metadata('testapp', labels=LABELS, external=False)
        }

        pytest.helpers.assert_any_call(post, INGRESSES_URI, expected_ingress)

    def test_deploy_new_ingress_dev_gke(self, request, delete, get, post):
        app_spec = request.getfuncargvalue("app_spec")
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.infrastructure = "gke"
        config.environment = "dev"
        config.ingress_suffixes = ["svc.dev.example.com", "k8s-gke.dev.example.com"]
        deployer = IngressDeployer(config)
        deployer.deploy(app_spec, LABELS)

        expected_ingress = {
            'spec': {
                'rules': [{
                    'host': 'testapp.svc.dev.example.com',
                    'http': {'paths': [{
                        'path': '/',
                        'backend': {
                            'serviceName': 'testapp',
                            'servicePort': 80
                        }}]
                    }
                }, {
                    'host': 'testapp.k8s-gke.dev.example.com',
                    'http': {'paths': [{
                        'path': '/',
                        'backend': {
                            'serviceName': 'testapp',
                            'servicePort': 80
                        }}]
                    }
                }],
                'tls': [],
            },
            'metadata': pytest.helpers.create_metadata('testapp', labels=LABELS, external=False)
        }

        pytest.helpers.assert_any_call(post, INGRESSES_URI, expected_ingress)

    @pytest.mark.parametrize("spec_name", (
            "app_spec_thrift_with_host",
            "app_spec_thrift"
    ))
    def test_remove_existing_ingress_if_not_needed(self, request, delete, post, deployer, spec_name):
        app_spec = request.getfuncargvalue(spec_name)

        deployer.deploy(app_spec, LABELS)

        pytest.helpers.assert_no_calls(post, INGRESSES_URI)
        pytest.helpers.assert_any_call(delete, INGRESSES_URI + "testapp")
