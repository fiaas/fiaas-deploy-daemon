#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

from .common import ObjectMeta
from .pod import PodSpec
from ..base import Model
from ..fields import Field

import six


class PodTemplateSpec(Model):
    metadata = Field(ObjectMeta)
    spec = Field(PodSpec)


class LabelsSelector(Model):
    matchLabels = Field(dict)


class RollbackConfig(Model):
    revision = Field(dict)


class DeploymentSpec(Model):
    replicas = Field(int, 1)
    selector = Field(LabelsSelector)
    template = Field(PodTemplateSpec)
    minReadySeconds = Field(six.text_type, alt_type=int)
    revisionHistoryLimit = Field(six.text_type, alt_type=int)
    paused = Field(six.text_type)


class Deployment(Model):
    class Meta:
        url_template = "/apis/extensions/v1beta1/namespaces/{namespace}/deployments/{name}"

    metadata = Field(ObjectMeta)
    spec = Field(DeploymentSpec)
    strategy = Field(six.text_type, "RollingUpdate")
