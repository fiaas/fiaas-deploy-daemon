#!/usr/bin/env python
# -*- coding: utf-8

from pprint import pformat

import pytest

from k8s.models.common import ObjectMeta
from k8s.models.pod import ContainerPort, Container, LocalObjectReference, Probe, HTTPGetAction, TCPSocketAction
from k8s.models.deployment import Deployment, DeploymentSpec, LabelsSelector, PodTemplateSpec, PodSpec
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
                DeploymentSpec.delete(name, namespace)
            except:
                pass

    def test_create_blank_deployment(self):
        deployment = Deployment(name=NAME)
        assert deployment.name == NAME
        assert deployment.as_dict()[u"metadata"][u"name"] == NAME

    @vcr.use_cassette()
    def test_lifecycle(self, logger):
        labels = {"test": "true"}
        object_meta = ObjectMeta(name=NAME, namespace=NAMESPACE, labels=labels)
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
        deployer_spec = DeploymentSpec(replicas=2, selector=LabelsSelector(matchLabels=labels), template=pod_template_spec)
        first = Deployment(name=NAME, metadata=object_meta, spec=deployer_spec)
        logger.debug(pformat(first.as_dict()))
        first.save()
