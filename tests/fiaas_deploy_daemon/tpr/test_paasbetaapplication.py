# coding: utf-8
from __future__ import absolute_import
import mock
import pytest

from k8s.client import NotFound

from k8s.models.common import ObjectMeta
from fiaas_deploy_daemon.tpr.types import (
    PaasbetaApplication, PaasbetaApplicationSpec, PaasApplicationConfig, Autoscaler, Prometheus, Resources,
    ResourceRequirements, Port, HealthChecks, HealthCheck, HttpCheck, Config
)

RESOURCE = 'paasbetaapplications'
NAMESPACE = 'my-namespace'
NAME = 'my_name'
API_VERSION = 'schibsted.io/v1beta'
API_BASE_PATH = "/apis/{api_version}/namespaces/{namespace}/{resource}/".format(
    api_version=API_VERSION, resource=RESOURCE, namespace=NAMESPACE
)
API_INSTANCE_PATH = "{base}{name}".format(base=API_BASE_PATH, name=NAME)


class TestService(object):
    def test_create_new_paasbetaapplication(self, post, get):
        get.side_effect = NotFound()
        pba = PaasbetaApplication(metadata=_create_default_metadata(), spec=_create_default_paasbetaapplicationspec())
        assert pba._new
        call_params = pba.as_dict()

        pba.save()

        pytest.helpers.assert_any_call(post, API_BASE_PATH, call_params)

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
        call_params = pba.as_dict()
        pba.save()
        pytest.helpers.assert_any_call(put, API_INSTANCE_PATH, call_params)

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
    return ObjectMeta(name=NAME, namespace=NAMESPACE, labels={"fiaas/deployment_id": "deployment_id"})
