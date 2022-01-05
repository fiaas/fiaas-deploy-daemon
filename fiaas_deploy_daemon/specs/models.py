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
from collections import namedtuple


class AppSpec(namedtuple("AppSpec", [
    "uid",
    "namespace",
    "name",
    "image",
    "autoscaler",
    "resources",
    "admin_access",
    "secrets_in_environment",
    "prometheus",
    "datadog",
    "ports",
    "health_checks",
    "teams",
    "tags",
    "deployment_id",
    "labels",
    "annotations",
    "ingresses",
    "strongbox",
    "singleton",
    "ingress_tls",
    "secrets",
    "app_config"
])):
    __slots__ = ()

    @property
    def version(self):
        if ":" in self.image:
            return self.image.split(":")[-1]
        else:
            raise RuntimeError('Version must be specified for docker image aka image:version')


ResourceRequirementSpec = namedtuple("ResourceRequirementSpec", [
    "cpu",
    "memory"])

ResourcesSpec = namedtuple("ResourcesSpec", [
    "limits",
    "requests"])

PrometheusSpec = namedtuple("PrometheusSpec", [
    "enabled",
    "port",
    "path"])

DatadogSpec = namedtuple("DatadogSpec", [
    "enabled",
    "tags"])

PortSpec = namedtuple("PortSpec", [
    "protocol",
    "name",
    "port",
    "target_port",
])

HealthCheckSpec = namedtuple("HealthCheckSpec", [
    "liveness",
    "readiness"])

CheckSpec = namedtuple("CheckSpec", [
    "execute",
    "http",
    "tcp",
    "initial_delay_seconds",
    "period_seconds",
    "success_threshold",
    "failure_threshold",
    "timeout_seconds"])

ExecCheckSpec = namedtuple("ExecCheckSpec", [
    "command"])

HttpCheckSpec = namedtuple("HttpCheckSpec", [
    "path",
    "port",
    "http_headers"])

TcpCheckSpec = namedtuple("TcpCheckSpec", [
    "port"])

AutoscalerSpec = namedtuple("AutoscalerSpec", [
    "enabled",
    "min_replicas",
    "max_replicas",
    "cpu_threshold_percentage"
])

LabelAndAnnotationSpec = namedtuple("LabelAndAnnotationSpec", [
    "deployment",
    "horizontal_pod_autoscaler",
    "ingress",
    "service",
    "service_account",
    "pod",
    "status",
])

IngressItemSpec = namedtuple("IngressItemSpec", [
    "host",
    "pathmappings",
    "annotations"
])

IngressPathMappingSpec = namedtuple("IngressPathMappingSpec", [
    "path",
    "port",
])

StrongboxSpec = namedtuple("StrongboxSpec", [
    "enabled",
    "iam_role",
    "aws_region",
    "groups",
])

SecretsSpec = namedtuple("SecretsSpec", [
    "type",
    "parameters",
    "annotations"
])

IngressTLSDeployerSpec = namedtuple("IngressTLSDeployerSpec", [
    "enabled",
    "certificate_issuer",
])
