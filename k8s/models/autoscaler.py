#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import six

from ..base import Model
from ..fields import Field, RequiredField
from .common import ObjectMeta


class CrossVersionObjectReference(Model):
    kind = RequiredField(six.text_type)
    name = RequiredField(six.text_type)
    apiVersion = Field(six.text_type)


class HorizontalPodAutoscalerSpec(Model):
    scaleTargetRef = RequiredField(CrossVersionObjectReference)
    minReplicas = Field(int, 2)
    maxReplicas = RequiredField(int)
    targetCPUUtilizationPercentage = Field(int, 50)


class HorizontalPodAutoscaler(Model):
    class Meta:
        url_template = "/apis/autoscaling/v1/namespaces/{namespace}/horizontalpodautoscalers/{name}"

    metadata = Field(ObjectMeta)
    spec = Field(HorizontalPodAutoscalerSpec)
