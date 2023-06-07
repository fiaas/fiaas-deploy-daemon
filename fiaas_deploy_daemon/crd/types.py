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
from k8s.base import Model, SelfModel
from k8s.fields import Field, RequiredField, ListField, JSONField
from k8s.models.apiextensions_v1_custom_resource_definition import CustomResourceSubresourceScale,\
    ExternalDocumentation
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


class FiaasApplicationStatusResult(Model):
    result = RequiredField(six.text_type)
    observedGeneration = Field(int, 0)
    deployment_id = Field(six.text_type)
    logs = ListField(six.text_type)


class FiaasApplicationStatusInline(Model):
    class Meta:
        list_url = "/apis/fiaas.schibsted.io/v1/applications"
        url_template = "/apis/fiaas.schibsted.io/v1/namespaces/{namespace}/applications/{name}/status"
        # watch_list_url = "/apis/fiaas.schibsted.io/v1/watch/applications"
        # watch_list_url_template = "/apis/fiaas.schibsted.io/v1/watch/namespaces/{namespace}/applications"
    apiVersion = Field(six.text_type, "fiaas.schibsted.io/v1")  # NOQA
    kind = Field(six.text_type, "Application")
    metadata = Field(ObjectMeta)
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


# Workaround to enable status on CRD we need to return {} 
# The default field returns {} as none
class EmptyField(Field):
    def _as_dict(self, value):
        return {}

class AdditionalCustomResourceSubresources(Model):
    scale = Field(CustomResourceSubresourceScale)
    # CustomResourceSubresourceStatus contains no fields,
    # so we use the dict type instead
    status = EmptyField(dict)

# When status is enabled there are other rules to,
# allowed root elements
class JSONSchemaPropsForStatus(Model):
    ref = Field(six.text_type, name='$ref')
    schema = Field(six.text_type, name='$schema')
    additionalItems = Field(SelfModel, alt_type=bool)
    additionalProperties = Field(SelfModel, alt_type=bool)
    # allOf = ListField(SelfModel)
    # anyOf = ListField(SelfModel)
    default = JSONField()
    definitions = Field(dict)
    dependencies = Field(dict)
    description = Field(six.text_type)
    enum = JSONField()
    example = JSONField()
    exclusiveMaximum = Field(bool)
    exclusiveMinimum = Field(bool)
    externalDocs = Field(ExternalDocumentation)
    format = Field(six.text_type)
    id = Field(six.text_type)
    items = Field(SelfModel, alt_type=list)
    maxItems = Field(int)
    maxLength = Field(int)
    maxProperties = Field(int)
    maximum = Field(int, alt_type=float)
    minItems = Field(int)
    minLength = Field(int)
    minProperties = Field(int)
    minimum = Field(int, alt_type=float)
    multipleOf = Field(int, alt_type=float)
    _not = Field(SelfModel)
    nullable = Field(bool)
    # oneOf = ListField(SelfModel)
    pattern = Field(six.text_type)
    patternProperties = Field(dict)
    properties = Field(dict)
    required = ListField(six.text_type)
    title = Field(six.text_type)
    type = Field(six.text_type)
    uniqueItems = Field(bool)
    x_kubernetes_embedded_resource = Field(bool, name='x-kubernetes-embedded-resource')
    x_kubernetes_int_or_string = Field(bool, name='x-kubernetes-int-or-string')
    # x_kubernetes_list_map_keys = ListField(six.text_type, name='x-kubernetes-list-map-keys')
    x_kubernetes_list_type = Field(six.text_type, name="x-kubernetes-list-type")
    x_kubernetes_map_type = Field(six.text_type, name='x-kubernetes-map-type')
    x_kubernetes_preserve_unknown_fields = Field(bool, name="x-kubernetes-preserve-unknown-fields")
