
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
# coding: utf-8


import mock
import pytest
from k8s.client import NotFound
from k8s.models.common import ObjectMeta
from requests import Response

from fiaas_deploy_daemon.crd.types import FiaasApplication, FiaasApplicationSpec

RESOURCE = 'applications'
NAMESPACE = 'my-namespace'
NAME = 'my_name'
API_VERSION = 'fiaas.schibsted.io/v1'
API_BASE_PATH = "/apis/{api_version}/namespaces/{namespace}/{resource}/".format(
    api_version=API_VERSION, resource=RESOURCE, namespace=NAMESPACE
)
API_INSTANCE_PATH = "{base}{name}".format(base=API_BASE_PATH, name=NAME)


class TestService(object):
    def test_create_new_fiaasapplication(self, post, get):
        get.side_effect = NotFound()
        fiaas_app = FiaasApplication(metadata=_create_default_metadata(), spec=_create_default_fiaasapplicationspec())
        assert fiaas_app._new
        expected_call = fiaas_app.as_dict()
        mock_response = mock.create_autospec(Response)
        mock_response.json.return_value = expected_call
        post.return_value = mock_response

        fiaas_app.save()

        pytest.helpers.assert_any_call(post, API_BASE_PATH, expected_call)

    def test_update_existing_fiaasapplication(self, put, get):
        get_response = mock.Mock()
        get_response.json.return_value = {
            "kind": "Application",
            "apiVersion": API_VERSION,
            "metadata": _create_default_metadata().as_dict(),
            "spec": _create_default_fiaasapplicationspec().as_dict()
        }
        get.return_value = get_response
        get.side_effect = None

        spec = _create_default_fiaasapplicationspec(
            replicas=2, host='example.org', ports=[{"protocol": 'tcp', "target_port": 1992}]
        )
        fiaas_app = FiaasApplication.get_or_create(metadata=_create_default_metadata(), spec=spec)

        assert not fiaas_app._new
        assert fiaas_app.spec.config["namespace"] == NAMESPACE
        assert fiaas_app.spec.config["replicas"] == 2
        assert fiaas_app.spec.config["host"] == 'example.org'
        assert fiaas_app.spec.config["ports"][0]["protocol"] == 'tcp'
        assert fiaas_app.spec.config["ports"][0]["target_port"] == 1992
        expected_call = fiaas_app.as_dict()
        mock_response = mock.create_autospec(Response)
        mock_response.json.return_value = expected_call
        put.return_value = mock_response

        fiaas_app.save()

        pytest.helpers.assert_any_call(put, API_INSTANCE_PATH, expected_call)

    def test_delete_fiaasapplication(self, delete):
        FiaasApplication.delete(NAME, NAMESPACE)
        pytest.helpers.assert_any_call(delete, API_INSTANCE_PATH)


def _create_default_fiaasapplicationspec(**kwargs):
    config = {
        'version':
            '2',
        'namespace':
            NAMESPACE,
        'admin_access':
            False,
        'has_secrets':
            True,
        'secrets_in_environment':
            False,
        'replicas':
            10,
        'autoscaler': {
            "enabled": True,
            "min_replicas": 2,
            "cpu_threshold_percentage": 75,
        },
        'host':
            'example.com',
        'prometheus': {
            'enabled': True, 'port': 'http', 'path': '/metrics/be/here'
        },
        'resources': {
            'limits': {
                'memory': '256M', 'cpu': '200m'
            },
            'requests': {
                'memory': '128M', 'cpu': '100m'
            }
        },
        'ports': [{
            'protocol': 'http', 'target_port': 1337, 'path': '/my_name'
        }],
        'healthchecks': {
            'liveness': {
                'http': {
                    'path': '/healthz', 'port': 'http', 'http_headers': {
                        'X-Foo': 'bar'
                    }
                }
            }
        },
        'config': {
            'volume': False, 'envs': [
                'CONFIG_THING',
                'ANOTHER_CONFIG_THING'
            ]
        }
    }
    config.update(kwargs)
    return FiaasApplicationSpec(application=NAME, image='example.com/group/image:tag', config=config)


def _create_default_metadata():
    return ObjectMeta(name=NAME, namespace=NAMESPACE, labels={"fiaas/deployment_id": "deployment_id"})
