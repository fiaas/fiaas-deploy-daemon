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


import six
from k8s.base import Model
from k8s.fields import Field, RequiredField, ListField
from k8s.models.common import ObjectMeta


class AdditionalLabelsOrAnnotations(Model):
    _global = Field(dict)
    deployment = Field(dict)
    horizontal_pod_autoscaler = Field(dict)
    ingress = Field(dict)
    service = Field(dict)
    service_account = Field(dict)
    pod = Field(dict)
    status = Field(dict)


class FiaasApplicationSpec(Model):
    application = RequiredField(six.text_type)
    image = RequiredField(six.text_type)
    config = RequiredField(dict)
    additional_labels = Field(AdditionalLabelsOrAnnotations)
    additional_annotations = Field(AdditionalLabelsOrAnnotations)


class FiaasApplicationStatusResult(Model):
    result = RequiredField(six.text_type)
    observed_generation = Field(int, 0)
    logs = ListField(six.text_type)
    deployment_id = Field(six.text_type)


class FiaasApplication(Model):
    class Meta:
        list_url = "/apis/fiaas.schibsted.io/v1/applications"
        url_template = "/apis/fiaas.schibsted.io/v1/namespaces/{namespace}/applications/{name}"
        watch_list_url = "/apis/fiaas.schibsted.io/v1/watch/applications"
        watch_list_url_template = "/apis/fiaas.schibsted.io/v1/watch/namespaces/{namespace}/applications"

    # Workaround for https://github.com/kubernetes/kubernetes/issues/44182
    apiVersion = Field(six.text_type, "fiaas.schibsted.io/v1")  # NOQA
    kind = Field(six.text_type, "Application")

    metadata = Field(ObjectMeta)
    spec = Field(FiaasApplicationSpec)
    status = Field(FiaasApplicationStatusResult)


class FiaasApplicationStatus(Model):
    class Meta:
        list_url = "/apis/fiaas.schibsted.io/v1/application-statuses"
        url_template = "/apis/fiaas.schibsted.io/v1/namespaces/{namespace}/application-statuses/{name}"
        watch_list_url = "/apis/fiaas.schibsted.io/v1/watch/application-statuses"
        watch_list_url_template = "/apis/fiaas.schibsted.io/v1/watch/namespaces/{namespace}/application-statuses"

    # Workaround for https://github.com/kubernetes/kubernetes/issues/44182
    apiVersion = Field(six.text_type, "fiaas.schibsted.io/v1")  # NOQA
    kind = Field(six.text_type, "ApplicationStatus")

    metadata = Field(ObjectMeta)
    result = Field(six.text_type)
    logs = ListField(six.text_type)
