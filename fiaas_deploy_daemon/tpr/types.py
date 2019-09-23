#!/usr/bin/env python
# -*- coding: utf-8

# Copyright 2017-2019 The FIAAS Authors
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#      http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import

import six
from k8s.base import Model
from k8s.fields import Field, RequiredField, ListField
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
    apiVersion = Field(six.text_type, "schibsted.io/v1beta")  # NOQA
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
    apiVersion = Field(six.text_type, "schibsted.io/v1beta")  # NOQA
    kind = Field(six.text_type, "PaasbetaStatus")

    metadata = Field(ObjectMeta)
    result = Field(six.text_type)
    logs = ListField(six.text_type)
