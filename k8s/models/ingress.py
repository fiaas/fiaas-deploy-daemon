#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import six

from .common import ObjectMeta
from ..base import Model
from ..fields import Field, ListField


class IngressBackend(Model):
    serviceName = Field(six.text_type)
    servicePort = Field(six.text_type)


class HTTPIngressPath(Model):
    path = Field(six.text_type)
    backend = Field(IngressBackend)


class HTTPIngressRuleValue(Model):
    paths = ListField(HTTPIngressPath)


class IngressRule(Model):
    host = Field(six.text_type)
    http = Field(HTTPIngressRuleValue)


class IngressTLS(Model):
    hosts = ListField(six.text_type)
    secretName = Field(six.text_type)


class IngressSpec(Model):
    backend = Field(IngressBackend)
    rules = ListField(IngressRule)
    tls = ListField(IngressTLS)


class Ingress(Model):
    class Meta:
        url_template = "/apis/extensions/v1beta1/namespaces/{namespace}/ingresses/{name}"

    metadata = Field(ObjectMeta)
    spec = Field(IngressSpec)
