#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

from .common import ObjectMeta
from .pod import PodTemplateSpec
from ..base import Model
from ..fields import Field


class ReplicationControllerSpec(Model):
    replicas = Field(int, 1)
    selector = Field(dict)
    template = Field(PodTemplateSpec)


class ReplicationController(Model):
    class Meta:
        url_template = "/api/v1/namespaces/{namespace}/replicationcontrollers/{name}"

    metadata = Field(ObjectMeta)
    spec = Field(ReplicationControllerSpec)
