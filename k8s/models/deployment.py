#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import six

from .common import ObjectMeta
from .pod import PodTemplateSpec
from ..base import Model
from ..fields import Field


class LabelSelector(Model):
    matchLabels = Field(dict)


class RollingUpdateDeployment(Model):
    maxUnavailable = Field(six.text_type)
    maxSurge = Field(six.text_type)


class DeploymentStrategy(Model):
    type = Field(six.text_type, "RollingUpdate")
    rollingUpdate = Field(RollingUpdateDeployment)


class DeploymentSpec(Model):
    replicas = Field(int, 1)
    selector = Field(LabelSelector)
    template = Field(PodTemplateSpec)
    strategy = Field(DeploymentStrategy)
    minReadySeconds = Field(six.text_type, alt_type=int)
    revisionHistoryLimit = Field(int)
    paused = Field(six.text_type)


class DeploymentStatus(Model):
    observedGeneration = Field(int)
    replicas = Field(int)
    updatedReplicas = Field(int)
    availableReplicas = Field(int)
    unavailableReplicas = Field(int)


class Deployment(Model):
    class Meta:
        url_template = "/apis/extensions/v1beta1/namespaces/{namespace}/deployments/{name}"

    metadata = Field(ObjectMeta)
    spec = Field(DeploymentSpec)
    status = Field(DeploymentStatus)
