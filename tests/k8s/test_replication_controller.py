#!/usr/bin/env python
# -*- coding: utf-8

from pprint import pformat

import pytest
from k8s.models.common import ObjectMeta
from k8s.models.pod import ContainerPort, Container, LocalObjectReference, Probe, HTTPGetAction, TCPSocketAction, PodTemplateSpec, PodSpec
from k8s.models.replication_controller import ReplicationController, ReplicationControllerSpec
from util import get_vcr

vcr = get_vcr(__file__)

NAME = "my-name"
NAMESPACE = "my-namespace"


@pytest.mark.usefixtures("logger", "k8s_config")
class TestRc(object):
    @vcr.use_cassette()
    def teardown(self):
        for name, namespace in ((NAME, "default"), (NAME, NAMESPACE)):
            try:
                ReplicationController.delete(name, namespace)
            except:
                pass

    def test_create_blank_rc(self):
        object_meta = ObjectMeta(name=NAME, namespace=NAMESPACE, labels={"test": "true"})
        rc = ReplicationController(metadata=object_meta)
        assert rc.metadata.name == NAME
        assert rc.as_dict()[u"metadata"][u"name"] == NAME

    @vcr.use_cassette()
    def test_lifecycle(self, logger):
        object_meta = ObjectMeta(name=NAME, namespace=NAMESPACE, labels={"test": "true"})
        container_port = ContainerPort(name="http5000", containerPort=5000)
        http = HTTPGetAction(path="/", port="http5000")
        liveness = Probe(httpGet=http)
        tcp = TCPSocketAction(port=5000)
        readiness = Probe(tcpSocket=tcp)
        container = Container(
            name="container",
            image="dummy_image",
            ports=[container_port],
            livenessProbe=liveness,
            readinessProbe=readiness
        )
        image_pull_secret = LocalObjectReference(name="image_pull_secret")
        pod_spec = PodSpec(containers=[container], imagePullSecrets=[image_pull_secret], serviceAccountName="default")
        pod_template_spec = PodTemplateSpec(metadata=object_meta, spec=pod_spec)
        rc_spec = ReplicationControllerSpec(replicas=2, selector={"test": "true"}, template=pod_template_spec)
        first = ReplicationController(metadata=object_meta, spec=rc_spec)
        logger.debug(pformat(first.as_dict()))
        first.save()

        second = ReplicationController.get(NAME, NAMESPACE)
        assert first.metadata.name == second.metadata.name
        assert first.metadata.namespace == second.metadata.namespace
