#!/usr/bin/env python
# -*- coding: utf-8

import mock
import pytest
from k8s.client import NotFound
from k8s.models.common import ObjectMeta
from k8s.models.service import Service, ServicePort, ServiceSpec
from util import assert_any_call_with_useful_error_message

SERVICE_NAMESPACE = 'my-namespace'
SERVICE_NAME = 'my_name'
SERVICES_URI = '/api/v1/namespaces/' + SERVICE_NAMESPACE + '/services/'


@pytest.mark.usefixtures("k8s_config")
class TestService(object):
    def test_create_blank_service(self):
        svc = create_default_service()
        assert svc.metadata.name == SERVICE_NAME
        assert svc.as_dict()[u"metadata"][u"name"] == SERVICE_NAME

    def test_create_blank_object_meta(self):
        meta = ObjectMeta(name=SERVICE_NAME, namespace=SERVICE_NAMESPACE, labels={"label": "value"})
        assert not hasattr(meta, "_name")
        assert meta.name == SERVICE_NAME
        assert meta.namespace == SERVICE_NAMESPACE
        assert meta.labels == {"label": "value"}
        assert meta.as_dict() == {
            "name": SERVICE_NAME,
            "namespace": SERVICE_NAMESPACE,
            "labels": {
                "label": "value"
            }
        }

    @mock.patch('k8s.base.ApiMixIn.get')
    @mock.patch('k8s.client.Client.post')
    def test_service_created_if_not_exists(self, post, get):
        get.side_effect = NotFound()
        service = create_default_service()
        service.save()
        assert service._new
        assert_any_call_with_useful_error_message(post, SERVICES_URI, service.as_dict())

    @mock.patch('k8s.client.Client.get')
    @mock.patch('k8s.client.Client.put')
    def test_get_or_create_service_not_new(self, put, get):
        service = create_default_service()

        mock_response = mock.Mock()
        mock_response.json.return_value = {
            "kind": "Service", "apiVersion": "v1", "metadata": {
                "name": SERVICE_NAME,
                "namespace": SERVICE_NAMESPACE,
                "selfLink": "/api/v1/namespaces/" + SERVICE_NAMESPACE + "/services/my-name",
                "uid": "cc562581-cbf5-11e5-b6ef-247703d2e388",
                "resourceVersion": "817",
                "creationTimestamp": "2016-02-05T10:47:06Z",
                "labels": {
                    "app": "test"
                }
            },
            "spec": {
                "ports": [
                    {
                        "name": "my-port", "protocol": "TCP", "port": 80, "targetPort": "name"
                    }
                ],
                "clusterIP": "10.0.0.54", "type": "ClusterIP", "sessionAffinity": "None"
            },
            "status": {
                "loadBalancer": {}
            }
        }
        get.return_value = mock_response

        metadata = ObjectMeta(name=SERVICE_NAME, namespace=SERVICE_NAMESPACE, labels={"app": "test"})
        port = ServicePort(name="my-port", port=80, targetPort="name")
        spec = ServiceSpec(ports=[port])

        from_api = Service.get_or_create(metadata=metadata, spec=spec)
        assert not from_api._new
        assert from_api.metadata.labels
        assert from_api.metadata.name == service.metadata.name
        from_api.save()
        assert_any_call_with_useful_error_message(put, SERVICES_URI + SERVICE_NAME, from_api.as_dict())

    @mock.patch('k8s.client.Client.delete')
    def test_service_deleted(self, delete):
        Service.delete(SERVICE_NAME, SERVICE_NAMESPACE)

        # call delete with service_name
        assert_any_call_with_useful_error_message(delete, (SERVICES_URI + SERVICE_NAME))


def create_default_service():
    metadata = ObjectMeta(name=SERVICE_NAME, namespace=SERVICE_NAMESPACE, labels={"app": "test"})
    port = ServicePort(name="my-port", port=80, targetPort="name")
    spec = ServiceSpec(ports=[port])
    return Service(metadata=metadata, spec=spec)


def create_simple_http_service_spec():
    return ServiceSpec(type="http")
