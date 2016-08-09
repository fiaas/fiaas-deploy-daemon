#!/usr/bin/env python
# -*- coding: utf-8

import pytest
import mock

from k8s.models.common import ObjectMeta
from k8s.models.service import Service, ServicePort, ServiceSpec
from k8s.client import NotFound
from util import assert_any_call_with_useful_error_message

service_namespace = 'my-namespace'
service_name = 'my_name'
services_uri = '/api/v1/namespaces/' + service_namespace + '/services/'


@pytest.mark.usefixtures("k8s_config")
class TestService(object):
    def test_create_blank_service(self):
        svc = create_default_service()
        assert svc.metadata.name == service_name
        assert svc.as_dict()[u"metadata"][u"name"] == service_name

    def test_create_blank_object_meta(self):
        meta = ObjectMeta(name=service_name, namespace=service_namespace, labels={"label": "value"})
        assert not hasattr(meta, "_name")
        assert meta.name == service_name
        assert meta.namespace == service_namespace
        assert meta.labels == {"label": "value"}
        assert meta.as_dict() == {
            "name": service_name,
            "namespace": service_namespace,
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
        assert_any_call_with_useful_error_message(post, services_uri, service.as_dict())

    @mock.patch('k8s.client.Client.get')
    @mock.patch('k8s.client.Client.put')
    def test_get_or_create_service_not_new(self, put, get):
        # service = create_default_service()

        mock_response = mock.Mock()
        mock_response.json.return_value = {
            "kind": "Service", "apiVersion": "v1", "metadata": {
                "name": service_name,
                "namespace": service_namespace,
                "selfLink": "/api/v1/namespaces/" + service_namespace + "/services/my-name",
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

        metadata = ObjectMeta(name=service_name, namespace=service_namespace, labels={"app": "test"})
        port = ServicePort(name="my-port", port=80, targetPort="name")
        spec = ServiceSpec(ports=[port])

        from_api = Service.get_or_create(name=service_name, metadata=metadata, spec=spec)
        assert not from_api._new
        assert from_api.metadata.labels
        #       comment in tests after MetaData-object has gotten name-fix which makes it obligatory.
        #       assert from_api.metadata.name == service.metadata.name
        from_api.save()

    #       assert_any_call_with_useful_error_message(put, services_uri + service_name, from_api.as_dict())

    @mock.patch('k8s.client.Client.delete')
    def test_service_deleted(self, delete):
        Service.delete(service_name, service_namespace)

        # call delete with service_name
        assert_any_call_with_useful_error_message(delete, (services_uri + service_name))


def create_default_service():
    metadata = ObjectMeta(name=service_name, namespace=service_namespace, labels={"app": "test"})
    port = ServicePort(name="my-port", port=80, targetPort="name")
    spec = ServiceSpec(ports=[port])
    return Service(metadata=metadata, spec=spec)


def create_simple_http_service_spec():
    return ServiceSpec(type="http")
