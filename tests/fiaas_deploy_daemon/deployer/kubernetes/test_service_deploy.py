#!/usr/bin/env python
# -*- coding: utf-8

import pytest
from fiaas_deploy_daemon.deployer.kubernetes.service import deploy_service
from mock import create_autospec
from requests import Response

SELECTOR = {'app': 'testapp'}
LABELS = {"service": "pass through"}
SERVICES_URI = '/api/v1/namespaces/default/services/'


def test_deploy_new_service(post, app_spec):
    deploy_service(app_spec, SELECTOR, LABELS)

    expected_service = {
        'spec': {
            'selector': SELECTOR,
            'type': 'NodePort',
            "loadBalancerSourceRanges": [
            ],
            'ports': [{
                'protocol': 'TCP',
                'targetPort': 8080,
                'name': 'http',
                'port': 80
            }],
            'sessionAffinity': 'None'
        },
        'metadata': pytest.helpers.create_metadata('testapp', labels=LABELS)
    }

    pytest.helpers.assert_any_call(post, SERVICES_URI, expected_service)


def test_deploy_new_service_with_multiple_ports(post, app_spec_thrift_and_http):
    deploy_service(app_spec_thrift_and_http, SELECTOR, LABELS)

    expected_service = {
        'spec': {
            'selector': SELECTOR,
            'type': 'NodePort',
            "loadBalancerSourceRanges": [],
            'ports': [
                {
                    'protocol': 'TCP',
                    'targetPort': 8080,
                    'name': 'http',
                    'port': 80
                },
                {
                    'protocol': 'TCP',
                    'targetPort': 7999,
                    'name': 'thrift',
                    'port': 7999
                },
            ],
            'sessionAffinity': 'None'
        },
        'metadata': pytest.helpers.create_metadata('testapp', labels=LABELS)
    }
    pytest.helpers.assert_any_call(post, SERVICES_URI, expected_service)


def test_update_service(get, post, put, app_spec):
    mock_response = create_autospec(Response)
    mock_response.json.return_value = {
        'spec': {
            'selector': SELECTOR,
            'type': 'NodePort',
            "loadBalancerSourceRanges": [
            ],
            'ports': [{
                'protocol': 'TCP',
                'targetPort': 8081,
                'name': 'http',
                'port': 81,
                'nodePort': 34567
            }],
            'sessionAffinity': 'None'
        },
        'metadata': pytest.helpers.create_metadata('testapp', labels=LABELS)
    }
    get.side_effect = None
    get.return_value = mock_response

    deploy_service(app_spec, SELECTOR, LABELS)

    expected_service = {
        'spec': {
            'selector': SELECTOR,
            'type': 'NodePort',
            "loadBalancerSourceRanges": [
            ],
            'ports': [{
                'protocol': 'TCP',
                'targetPort': 8080,
                'name': 'http',
                'port': 80,
                'nodePort': 34567
            }],
            'sessionAffinity': 'None'
        },
        'metadata': pytest.helpers.create_metadata('testapp', labels=LABELS)
    }

    pytest.helpers.assert_no_calls(post)
    pytest.helpers.assert_any_call(put, SERVICES_URI+"testapp", expected_service)
