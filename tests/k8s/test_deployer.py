#!/usr/bin/env python
# -*- coding: utf-8

from pprint import pformat

import pytest
from k8s.models.common import ObjectMeta
from k8s.models.deployment import Deployment, DeploymentSpec, LabelSelector
from k8s.models.pod import ContainerPort, Container, LocalObjectReference, Probe, HTTPGetAction, TCPSocketAction, \
    PodTemplateSpec, PodSpec
from util import get_vcr

vcr = get_vcr(__file__)

NAME = "my-name"
NAMESPACE = "my-namespace"


@pytest.mark.usefixtures("logger", "k8s_config")
class TestDeployer(object):
    def test_create_blank_deployment(self):
        object_meta = ObjectMeta(name=NAME, namespace=NAMESPACE)
        deployment = Deployment(metadata=object_meta)
        assert deployment.as_dict()[u"metadata"][u"name"] == NAME

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
        deployer_spec = DeploymentSpec(replicas=2, selector=LabelSelector(matchLabels=labels),
                                       template=pod_template_spec, revisionHistoryLimit=5)
        first = Deployment(metadata=object_meta, spec=deployer_spec)
        logger.debug(pformat(first.as_dict()))

        pytest.helpers.assert_dicts(first.as_dict(), {
            u"metadata": {
                u"labels": {
                    u"test": u"true"
                },
                u"namespace": u"my-namespace",
                u"name": u"my-name"
            },
            u"spec": {
                u"replicas": 2,
                u"revisionHistoryLimit": 5,
                u"template": {
                    u"spec": {
                        u"dnsPolicy": u"ClusterFirst",
                        u"serviceAccountName": u"default",
                        u"restartPolicy": u"Always",
                        u"volumes": [],
                        u"imagePullSecrets": [
                            {
                                u"name": u"image_pull_secret"
                            }
                        ],
                        u"containers": [
                            {
                                u"livenessProbe": {
                                    u"initialDelaySeconds": 5,
                                    u"httpGet": {
                                        u"path": u"/",
                                        u"scheme": u"HTTP",
                                        u"port": u"http5000"
                                    }
                                },
                                u"name": u"container",
                                u"image": u"dummy_image",
                                u"volumeMounts": [],
                                u"env": [],
                                u"imagePullPolicy": u"IfNotPresent",
                                u"readinessProbe": {
                                    u"initialDelaySeconds": 5,
                                    u"tcpSocket": {
                                        u"port": 5000
                                    }
                                },
                                u"ports": [
                                    {
                                        u"protocol": u"TCP",
                                        u"containerPort": 5000,
                                        u"name": u"http5000"
                                    }
                                ]
                            }
                        ]
                    },
                    u"metadata": {
                        u"labels": {
                            u"test": u"true"
                        },
                        u"namespace": u"my-namespace",
                        u"name": u"my-name"
                    }
                },
                u"selector": {
                    u"matchLabels": {
                        u"test": u"true"
                    }
                }
            }
        })
