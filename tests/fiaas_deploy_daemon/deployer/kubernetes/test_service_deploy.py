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
import pytest
from mock import create_autospec
from requests import Response

from fiaas_deploy_daemon.config import Configuration
from fiaas_deploy_daemon.deployer.kubernetes.service import ServiceDeployer
from fiaas_deploy_daemon.specs.models import LabelAndAnnotationSpec

SELECTOR = {'app': 'testapp'}
LABELS = {"service": "pass through"}
SERVICES_URI = '/api/v1/namespaces/default/services/'


class TestServiceDeployer(object):
    @pytest.fixture(params=("ClusterIP", "NodePort", "LoadBalancer"))
    def service_type(self, request):
        return request.param

    @pytest.fixture
    def deployer(self, service_type):
        config = create_autospec(Configuration([]), spec_set=True)
        config.service_type = service_type
        return ServiceDeployer(config)

    @pytest.mark.usefixtures("get")
    def test_deploy_new_service(self, deployer, service_type, post, app_spec):
        expected_service = {
            'spec': {
                'selector': SELECTOR,
                'type': service_type,
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
        mock_response = create_autospec(Response)
        mock_response.json.return_value = expected_service
        post.return_value = mock_response

        deployer.deploy(app_spec, SELECTOR, LABELS)

        pytest.helpers.assert_any_call(post, SERVICES_URI, expected_service)

    @pytest.mark.usefixtures("get")
    def test_deploy_new_service_with_custom_labels_and_annotations(self, deployer, service_type, post, app_spec):
        expected_labels = {"custom": "label"}
        expected_annotations = {"custom": "annotation"}

        expected_service = {
            'spec': {
                'selector': SELECTOR,
                'type': service_type,
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
            'metadata': pytest.helpers.create_metadata('testapp', labels=expected_labels,
                                                       annotations=expected_annotations)
        }
        mock_response = create_autospec(Response)
        mock_response.json.return_value = expected_service
        post.return_value = mock_response

        labels = LabelAndAnnotationSpec(deployment={}, horizontal_pod_autoscaler={}, ingress={},
                                        service=expected_labels, pod={}, status={})
        annotations = LabelAndAnnotationSpec(deployment={}, horizontal_pod_autoscaler={}, ingress={},
                                             service=expected_annotations, pod={}, status={})
        app_spec_custom_labels_and_annotations = app_spec._replace(labels=labels, annotations=annotations)

        deployer.deploy(app_spec_custom_labels_and_annotations, SELECTOR, {})

        pytest.helpers.assert_any_call(post, SERVICES_URI, expected_service)

    @pytest.mark.usefixtures("get")
    def test_deploy_new_service_with_multiple_ports(self, deployer, service_type, post, app_spec_thrift_and_http):
        expected_service = {
            'spec': {
                'selector': SELECTOR,
                'type': service_type,
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
            'metadata': pytest.helpers.create_metadata('testapp', labels=LABELS,
                                                       annotations={"fiaas/tcp_port_names": "thrift"})
        }
        mock_response = create_autospec(Response)
        mock_response.json.return_value = expected_service
        post.return_value = mock_response

        deployer.deploy(app_spec_thrift_and_http, SELECTOR, LABELS)

        pytest.helpers.assert_any_call(post, SERVICES_URI, expected_service)

    @pytest.mark.usefixtures("get")
    def test_deploy_new_service_with_multiple_tcp_ports(self, deployer, service_type, post,
                                                        app_spec_multiple_thrift_ports):
        expected_service = {
            'spec': {
                'selector': SELECTOR,
                'type': service_type,
                "loadBalancerSourceRanges": [],
                'ports': [
                    {
                        'protocol': 'TCP',
                        'targetPort': 7999,
                        'name': 'thrift1',
                        'port': 7999
                    },
                    {
                        'protocol': 'TCP',
                        'targetPort': 8000,
                        'name': 'thrift2',
                        'port': 8000
                    },
                ],
                'sessionAffinity': 'None'
            },
            'metadata': pytest.helpers.create_metadata('testapp', labels=LABELS,
                                                       annotations={"fiaas/tcp_port_names": "thrift1,thrift2"})
        }
        mock_response = create_autospec(Response)
        mock_response.json.return_value = expected_service
        post.return_value = mock_response

        deployer.deploy(app_spec_multiple_thrift_ports, SELECTOR, LABELS)

        pytest.helpers.assert_any_call(post, SERVICES_URI, expected_service)

    def test_update_service(self, deployer, service_type, get, post, put, app_spec):
        mock_response = create_autospec(Response)
        mock_response.json.return_value = {
            'spec': {
                'selector': SELECTOR,
                'type': service_type,
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

        expected_service = {
            'spec': {
                'selector': SELECTOR,
                'type': service_type,
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
        mock_response = create_autospec(Response)
        mock_response.json.return_value = expected_service
        put.return_value = mock_response

        deployer.deploy(app_spec, SELECTOR, LABELS)

        pytest.helpers.assert_no_calls(post)
        pytest.helpers.assert_any_call(put, SERVICES_URI + "testapp", expected_service)

    def test_dont_deploy_service_with_no_ports(self, deployer, post, delete, app_spec_no_ports):
        deployer.deploy(app_spec_no_ports, SELECTOR, LABELS)

        pytest.helpers.assert_no_calls(post)
        pytest.helpers.assert_any_call(delete, SERVICES_URI + app_spec_no_ports.name)
