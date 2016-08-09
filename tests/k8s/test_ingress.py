#!/usr/bin/env python
# -*- coding: utf-8

from pprint import pformat

import pytest

from k8s.models.common import ObjectMeta
from k8s.models.ingress import Ingress, IngressSpec, IngressRule, IngressBackend, HTTPIngressPath, HTTPIngressRuleValue
from util import get_vcr

vcr = get_vcr(__file__)

NAME = "my-name"
NAMESPACE = "my-namespace"


@pytest.mark.usefixtures("logger", "k8s_config")
class TestIngress(object):
    @vcr.use_cassette()
    def teardown(self):
        for name, namespace in ((NAME, "default"), (NAME, NAMESPACE)):
            try:
                Ingress.delete(name, namespace)
            except:
                pass

    def test_create_blank(self):
        object_meta = ObjectMeta(name=NAME, namespace=NAMESPACE, labels={"test": "true"})
        ingress = Ingress(metadata=object_meta)
        assert ingress.metadata.name == NAME

    @vcr.use_cassette()
    def test_lifecylce(self, logger):
        object_meta = ObjectMeta(name=NAME, namespace=NAMESPACE, labels={"test": "true"})
        ingress_backend = IngressBackend(serviceName="dummy", servicePort="http")
        http_ingress_path = HTTPIngressPath(path="/", backend=ingress_backend)
        http_ingress_rule = HTTPIngressRuleValue(paths=[http_ingress_path])
        ingress_rule = IngressRule(host="dummy.example.com", http=http_ingress_rule)
        ingress_spec = IngressSpec(rules=[ingress_rule])
        first = Ingress(metadata=object_meta, spec=ingress_spec)
        logger.debug(pformat(first.as_dict()))
        first.save()

        second = Ingress.get(NAME, NAMESPACE)
        assert first.metadata.name == second.metadata.name
        assert first.spec == second.spec
