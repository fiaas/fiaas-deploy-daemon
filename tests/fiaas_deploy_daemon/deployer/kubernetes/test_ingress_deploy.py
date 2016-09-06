#!/usr/bin/env python
# -*- coding: utf-8
import mock
import pytest

from fiaas_deploy_daemon.deployer.kubernetes.ingress import IngressDeployer

LABELS = {"ingress_deployer": "pass through"}
INGRESSES_URI = '/apis/extensions/v1beta1/namespaces/default/ingresses/'


class TestIngressDeployer(object):
    @pytest.fixture
    def deployer(self):
        config = mock.NonCallableMagicMock()
        config.target_cluster = "test"
        return IngressDeployer(config)

    @pytest.mark.parametrize("host,expected", [
        ("www.finn.no", "test.finn.no"),
        ("m.finn.no", "test.m.finn.no"),
        ("kart.finn.no", "test.kart.finn.no")
    ])
    def test_make_ingress_host(self, deployer, host, expected):
        assert deployer._make_ingress_host(host) == expected

    def test_deploy_new_ingress(self, post, deployer, app_spec_with_host):
        deployer.deploy(app_spec_with_host, LABELS)

        expected_ingress = {
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

        pytest.helpers.assert_any_call(post, INGRESSES_URI, expected_ingress)

    def test_no_host_no_ingress(self, post, deployer, app_spec):
        deployer.deploy(app_spec, {})

        pytest.helpers.assert_no_calls(post, INGRESSES_URI)

    def test_remove_existing_ingress_if_no_host(self, delete, get, post, deployer, app_spec):
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
