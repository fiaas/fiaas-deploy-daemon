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
        return IngressDeployer(config)

    @pytest.mark.parametrize("host,expected", [
        ("www.finn.no", "test.finn.no"),
        ("m.finn.no", "test.m.finn.no"),
        ("kart.finn.no", "test.kart.finn.no"),
        (None, "testapp.127.0.0.1.xip.io")
    ])
    def test_make_ingress_host(self, deployer, app_spec, host, expected):
        assert deployer._make_ingress_host(app_spec._replace(host=host)) == expected

    @pytest.mark.parametrize("host,expected", [
        ("www.finn.no", "www.finn.no"),
        ("m.finn.no", "m.finn.no"),
        ("kart.finn.no", "kart.finn.no"),
        (None, "testapp.k8s1-prod1.z01.finn.no"),
    ])
    def test_make_ingress_host_prod(self, app_spec, host, expected):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.infrastructure = "diy"
        config.environment = "prod"
        deployer = IngressDeployer(config)
        assert deployer._make_ingress_host(app_spec._replace(host=host)) == expected

    @pytest.mark.parametrize("spec_name,host,external", (
            ("app_spec_with_host", "test.finn.no", True),
            ("app_spec", "testapp.127.0.0.1.xip.io", False)
    ))
    def test_deploy_new_ingress(self, request, post, deployer, spec_name, host, external):
        app_spec = request.getfuncargvalue(spec_name)
        deployer.deploy(app_spec, LABELS)

        expected_ingress = {
            'spec': {
                'rules': [{
                    'host': host,
                    'http': {'paths': [{
                        'path': '/',
                        'backend': {
                            'serviceName': 'testapp',
                            'servicePort': 80
                        }}]
                    }
                }]
            },
            'metadata': pytest.helpers.create_metadata('testapp', labels=LABELS, external=external)
        }

        pytest.helpers.assert_any_call(post, INGRESSES_URI, expected_ingress)

    def test_deploy_new_ingress_dev_gke(self, request, delete, get, post):
        app_spec = request.getfuncargvalue("app_spec")
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.infrastructure = "gke"
        config.environment = "dev"
        deployer = IngressDeployer(config)
        deployer.deploy(app_spec, LABELS)

        expected_ingress = {
            'spec': {
                'rules': [{
                    'host': 'testapp.k8s-gke.dev.finn.no',
                    'http': {'paths': [{
                        'path': '/',
                        'backend': {
                            'serviceName': 'testapp',
                            'servicePort': 80
                        }}]
                    }
                }, {
                    'host': 'testapp.svc.dev.finn.no',
                    'http': {'paths': [{
                        'path': '/',
                        'backend': {
                            'serviceName': 'testapp',
                            'servicePort': 80
                        }}]
                    }
                }, {
                    'host': 'testapp.k8s.dev.finn.no',
                    'http': {'paths': [{
                        'path': '/',
                        'backend': {
                            'serviceName': 'testapp',
                            'servicePort': 80
                        }}]
                    }
                },
                ]
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
                    }
                }]
            },
            'metadata': pytest.helpers.create_metadata('testapp', labels=LABELS)
        }

        deployer.deploy(app_spec, LABELS)

        pytest.helpers.assert_no_calls(post, INGRESSES_URI)
        pytest.helpers.assert_any_call(delete, INGRESSES_URI + "testapp")
