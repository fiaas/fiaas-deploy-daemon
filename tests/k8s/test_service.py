#!/usr/bin/env python
# -*- coding: utf-8

import pytest

from k8s.models.common import ObjectMeta
from k8s.models.service import Service, ServicePort, ServiceSpec
from util import get_vcr

vcr = get_vcr(__file__)


@pytest.mark.usefixtures("k8s_config")
class TestService(object):
    @vcr.use_cassette()
    def teardown(self):
        for name, namespace in (("my-name", "default"), ("my-name", "my-namespace")):
            try:
                Service.delete(name, namespace)
            except:
                pass

    def test_create_blank_service(self):
        meta = ObjectMeta(name="my-name", namespace="my-namespace", labels={"label": "value"})
        svc = Service(metadata=meta)
        assert svc.metadata.name == "my-name"
        assert svc.as_dict()[u"metadata"][u"name"] == "my-name"

    def test_create_blank_object_meta(self):
        meta = ObjectMeta(name="my-name", namespace="my-namespace", labels={"label": "value"})
        assert not hasattr(meta, "_name")
        assert meta.name == "my-name"
        assert meta.namespace == "my-namespace"
        assert meta.labels == {"label": "value"}
        assert meta.as_dict() == {
            "name": "my-name",
            "namespace": "my-namespace",
            "labels": {
                "label": "value"
            }
        }

    @vcr.use_cassette()
    def test_service_lifecycle(self):
        metadata = ObjectMeta(name="my-name", namespace="my-namespace", labels={"app": "test"})
        port = ServicePort(name="my-port", port=80, targetPort="name")
        spec = ServiceSpec(ports=[port])
        original = Service(metadata=metadata, spec=spec)
        original.save()
        from_api = Service.get("my-name", "my-namespace")
        assert original.metadata.name == from_api.metadata.name
        assert original.metadata.namespace == from_api.metadata.namespace
        from_api.metadata.labels["added"] = "label"
        from_api.save()
        third = Service.get("my-name", "my-namespace")
        assert from_api.metadata.labels == third.metadata.labels

    @vcr.use_cassette()
    def test_get_or_create(self):
        metadata = ObjectMeta(name="my-name", namespace="my-namespace", labels={"app": "test"})
        port = ServicePort(name="my-port", port=80, targetPort="name")
        spec = ServiceSpec(ports=[port])
        original = Service.get_or_create(metadata=metadata, spec=spec)
        assert original._new
        original.save()
        spec.clusterIP = "10.0.0.111"
        port.name = "other-name"
        second = Service.get_or_create(metadata=metadata, spec=spec)
        assert not second._new
        assert original.metadata.name == second.metadata.name
        assert second.spec.clusterIP != spec.clusterIP
        assert second.spec.ports[0].name == "other-name"
