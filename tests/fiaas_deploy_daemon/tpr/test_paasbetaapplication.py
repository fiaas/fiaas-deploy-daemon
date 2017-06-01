# coding: utf-8
from __future__ import absolute_import
import mock
import pytest

from k8s.client import NotFound
from k8s import config

from k8s.models.common import ObjectMeta
from fiaas_deploy_daemon.tpr.paasbetaapplication import (
    PaasbetaApplication, PaasbetaApplicationSpec, PaasApplicationConfig, Autoscaler, Prometheus, Resources,
    ResourceRequirements, Port, HealthChecks, HealthCheck, HttpCheck, Config
)

RESOURCE = 'paasbetaapplications'
APIVERSION = 'schibsted.io/v1beta'
NAMESPACE = 'my-namespace'
NAME = 'my_name'
API_VERSION = 'schibsted.io/v1beta'
API_BASE_PATH = "/apis/{api_version}/namespaces/{namespace}/{resource}/".format(
    api_version=API_VERSION, resource=RESOURCE, namespace=NAMESPACE
)
API_INSTANCE_PATH = "{base}{name}".format(base=API_BASE_PATH, name=NAME)


@pytest.fixture
def k8s_config(monkeypatch):
    """Configure k8s for test-runs"""
    monkeypatch.setattr(config, "api_server", "https://10.0.0.1")
    monkeypatch.setattr(config, "api_token", "password")
    monkeypatch.setattr(config, "verify_ssl", False)


@pytest.mark.usefixtures("k8s_config")
class TestService(object):

    @pytest.fixture(autouse=True)
    def get(self):
        with mock.patch('k8s.client.Client.get') as mockk:
            yield mockk

    @pytest.fixture(autouse=True)
    def post(self):
        with mock.patch('k8s.client.Client.post') as mockk:
            yield mockk

    @pytest.fixture(autouse=True)
    def put(self):
        with mock.patch('k8s.client.Client.put') as mockk:
            yield mockk

    @pytest.fixture(autouse=True)
    def delete(self):
        with mock.patch('k8s.client.Client.delete') as mockk:
            yield mockk

    def test_create_new_paasbetaapplication(self, post, get):
        get.side_effect = NotFound()
        pba = PaasbetaApplication(metadata=_create_default_metadata(), spec=_create_default_paasbetaapplicationspec())
        pba.save()

        assert pba._new
        pytest.helpers.assert_any_call(post, API_BASE_PATH, pba.as_dict())

    def test_update_existing_paasbetaapplication(self, put, get):
        get_response = mock.Mock()
        get_response.json.return_value = {
            "kind": "PaasbetaApplication",
            "apiVersion": API_VERSION,
            "metadata": _create_default_metadata().as_dict(),
            "spec": _create_default_paasbetaapplicationspec().as_dict()
        }
        get.return_value = get_response

        spec = _create_default_paasbetaapplicationspec(
            replicas=2, host='example.org', ports=[Port(protocol='tcp', target_port=1992)]
        )
        pba = PaasbetaApplication.get_or_create(metadata=_create_default_metadata(), spec=spec)

        assert not pba._new
        assert pba.spec.config.namespace == NAMESPACE
        assert pba.spec.config.replicas == 2
        assert pba.spec.config.host == 'example.org'
        assert pba.spec.config.ports[0].protocol == 'tcp'
        assert pba.spec.config.ports[0].target_port == 1992
        pba.save()
        pytest.helpers.assert_any_call(put, API_INSTANCE_PATH, pba.as_dict())

    def test_delete_paasbetaapplication(self, delete):
        PaasbetaApplication.delete(NAME, NAMESPACE)
        pytest.helpers.assert_any_call(delete, API_INSTANCE_PATH)


def _create_default_paasbetaapplicationspec(**kwargs):
    config = {
        'version':
            '2',
        'namespace':
            NAMESPACE,
        'admin_access':
            False,
        'has_secrets':
            True,
        'replicas':
            10,
        'autoscaler':
            Autoscaler(enabled=True, min_replicas=2, cpu_threshold_percentage=75),
        'host':
            'example.com',
        'prometheus':
            Prometheus(enabled=True, port='http', path='/metrics/be/here'),
        'resources':
            Resources(
                limits=ResourceRequirements(memory='256M', cpu='200m'),
                requests=ResourceRequirements(memory='128M', cpu='100m')
            ),
        'ports': [Port(protocol='http', target_port=1337, path='/my_name')],
        'healthchecks':
            HealthChecks(
                liveness=HealthCheck(http=HttpCheck(path='/healthz', port='http', http_headers={'X-Foo': 'bar'}))
            ),
        'config':
            Config(volume=False, envs=['CONFIG_THING', 'ANOTHER_CONFIG_THING'])
    }
    config.update(kwargs)
    return PaasbetaApplicationSpec(application=NAME, image='example.com/group/image:tag',
                                   config=PaasApplicationConfig(**config))


def _create_default_metadata():
    return ObjectMeta(name=NAME, namespace=NAMESPACE, annotations={"fiaas/deployment_id": "deployment_id"})
