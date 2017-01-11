#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import six

from .common import ObjectMeta
from ..base import Model
from ..fields import Field, OnceField, ListField


class ServicePort(Model):
    name = Field(six.text_type)
    protocol = Field(six.text_type, "TCP")
    port = Field(int)
    targetPort = Field(six.text_type)
    nodePort = Field(int)


class ServiceSpec(Model):
    ports = ListField(ServicePort)
    selector = Field(dict)
    clusterIP = OnceField(six.text_type)
    loadBalancerIP = OnceField(six.text_type)
    type = Field(six.text_type, "ClusterIP")
    sessionAffinity = Field(six.text_type, "None")
    loadBalancerSourceRanges = ListField(six.text_type)


class Service(Model):
    class Meta:
        url_template = "/api/v1/namespaces/{namespace}/services/{name}"

    metadata = Field(ObjectMeta)
    spec = Field(ServiceSpec)
