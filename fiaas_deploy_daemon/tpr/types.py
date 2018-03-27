#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import six

from k8s.base import Model
from k8s.fields import Field, RequiredField
from k8s.models.common import ObjectMeta


class PaasbetaApplicationSpec(Model):
    application = RequiredField(six.text_type)
    image = RequiredField(six.text_type)
    config = RequiredField(dict)


class PaasbetaApplication(Model):
    class Meta:
        list_url = "/apis/schibsted.io/v1beta/paasbetaapplications"
        url_template = "/apis/schibsted.io/v1beta/namespaces/{namespace}/paasbetaapplications/{name}"
        watch_list_url = "/apis/schibsted.io/v1beta/watch/paasbetaapplications"
        watch_list_url_template = "/apis/schibsted.io/v1beta/watch/namespaces/{namespace}/paasbetaapplications"

    # Workaround for https://github.com/kubernetes/kubernetes/issues/44182
    apiVersion = Field(six.text_type, "schibsted.io/v1beta")
    kind = Field(six.text_type, "PaasbetaApplication")

    metadata = Field(ObjectMeta)
    spec = Field(PaasbetaApplicationSpec)


class PaasbetaStatus(Model):
    class Meta:
        list_url = "/apis/schibsted.io/v1beta/paasbetastatuses"
        url_template = "/apis/schibsted.io/v1beta/namespaces/{namespace}/paasbetastatuses/{name}"
        watch_list_url = "/apis/schibsted.io/v1beta/watch/paasbetastatuses"
        watch_list_url_template = "/apis/schibsted.io/v1beta/watch/namespaces/{namespace}/paasbetastatuses"

    # Workaround for https://github.com/kubernetes/kubernetes/issues/44182
    apiVersion = Field(six.text_type, "schibsted.io/v1beta")
    kind = Field(six.text_type, "PaasbetaStatus")

    metadata = Field(ObjectMeta)
    result = Field(six.text_type)
