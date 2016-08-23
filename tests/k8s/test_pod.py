#!/usr/bin/env python
# -*- coding: utf-8

from pprint import pformat

import pytest
from k8s.models.common import ObjectMeta
from k8s.models.pod import Pod, ContainerPort, Container, LocalObjectReference, PodSpec, Volume, VolumeMount, SecretVolumeSource
from util import get_vcr

vcr = get_vcr(__file__)

NAME = "my-name"
NAMESPACE = "my-namespace"


@pytest.mark.usefixtures("logger", "k8s_config")
class TestPod(object):
    @vcr.use_cassette()
    def teardown(self):
        for name, namespace in ((NAME, "default"), (NAME, NAMESPACE)):
            try:
                Pod.delete(name, namespace)
            except:
                pass

    @vcr.use_cassette()
    def test_lifecycle(self, logger):
        object_meta = ObjectMeta(name=NAME, namespace=NAMESPACE, labels={"test": "true", "app": NAME})
        container_port = ContainerPort(name="http5000", containerPort=5000)
        secrets_volume_mounts = [VolumeMount(name=NAME, readOnly=True, mountPath="/var/run/secrets/kubernetes.io/kubernetes-secrets")]
        secret_volumes = [Volume(name=NAME, secret=SecretVolumeSource(secretName=NAME))]
        container = Container(name="container", image="dummy_image", ports=[container_port], volumeMounts=secrets_volume_mounts)
        image_pull_secret = LocalObjectReference(name="image_pull_secret")
        pod_spec = PodSpec(containers=[container], imagePullSecrets=[image_pull_secret],
                           volumes=secret_volumes, serviceAccountName="default")
        first = Pod(metadata=object_meta, spec=pod_spec)
        logger.debug(pformat(first.as_dict()))
        first.save()

        pods = Pod.find(NAME, NAMESPACE)
        assert len(pods) == 1
        second = pods[0]
        assert first.metadata.name == second.metadata.name
        assert first.metadata.namespace == second.metadata.namespace
