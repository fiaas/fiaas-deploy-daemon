#!/usr/bin/env python
# -*- coding: utf-8

# Copyright 2017-2024 The FIAAS Authors
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

from k8s.base import Model
from k8s.fields import Field, ListField
from k8s.models.common import ObjectMeta, LabelSelector
from k8s.models.deployment import PodTemplateSpec
from k8s.models.pod import ResourceRequirements


class RollingUpdateStatefulSetStrategy(Model):
    partition = Field(int)


class StatefulSetUpdateStrategy(Model):
    type = Field(str, "RollingUpdate")
    rollingUpdate = Field(RollingUpdateStatefulSetStrategy)


class PersistentVolumeClaimSpec(Model):
    accessModes = ListField(str)
    resources = Field(ResourceRequirements)
    storageClassName = Field(str)


class PersistentVolumeClaim(Model):
    metadata = Field(ObjectMeta)
    spec = Field(PersistentVolumeClaimSpec)


class StatefulSetSpec(Model):
    serviceName = Field(str)
    replicas = Field(int, 1)
    selector = Field(LabelSelector)
    template = Field(PodTemplateSpec)
    updateStrategy = Field(StatefulSetUpdateStrategy)
    podManagementPolicy = Field(str, "OrderedReady")
    volumeClaimTemplates = ListField(PersistentVolumeClaim)


class StatefulSet(Model):
    class Meta:
        list_url = "/apis/apps/v1/statefulsets"
        url_template = "/apis/apps/v1/namespaces/{namespace}/statefulsets/{name}"

    metadata = Field(ObjectMeta)
    spec = Field(StatefulSetSpec)

