#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import six

from k8s.base import Model
from k8s.fields import Field, RequiredField, ListField
from k8s.models.common import ObjectMeta


class Config(Model):
    volume = Field(bool)
    envs = ListField(six.text_type)


class ExecuteCheck(Model):
    command = Field(six.text_type)


class HttpCheck(Model):
    path = Field(six.text_type)
    port = Field(six.text_type)
    http_headers = Field(dict)


class TcpCheck(Model):
    port = Field(six.text_type)


class HealthCheck(Model):
    execute = Field(ExecuteCheck)
    http = Field(HttpCheck)
    tcp = Field(TcpCheck)
    initial_delay_seconds = Field(int)
    period_seconds = Field(int)
    success_threshold = Field(int)
    timeout_seconds = Field(int)


class HealthChecks(Model):
    liveness = Field(HealthCheck)
    readiness = Field(HealthCheck)


class Port(Model):
    protocol = Field(six.text_type)
    name = Field(six.text_type)
    port = Field(int)
    target_port = Field(int)
    path = Field(six.text_type)


class ResourceRequirements(Model):
    memory = Field(six.text_type)
    cpu = Field(six.text_type)


class Resources(Model):
    limits = Field(ResourceRequirements)
    requests = Field(ResourceRequirements)


class Prometheus(Model):
    enabled = Field(bool)
    port = Field(six.text_type)
    path = Field(six.text_type)


class Autoscaler(Model):
    enabled = Field(bool)
    min_replicas = Field(int)
    cpu_threshold_percentage = Field(int)


class PaasApplicationConfig(Model):
    version = Field(int)
    namespace = Field(six.text_type)
    admin_access = Field(bool)
    has_secrets = Field(bool)
    replicas = Field(int)
    autoscaler = Field(Autoscaler)
    host = Field(six.text_type)
    prometheus = Field(Prometheus)
    resources = Field(Resources)
    ports = ListField(Port)
    healthchecks = Field(HealthChecks)
    config = Field(Config)


class PaasbetaApplicationSpec(Model):
    application = RequiredField(six.text_type)
    image = RequiredField(six.text_type)
    config = RequiredField(PaasApplicationConfig)


class PaasbetaApplication(Model):
    class Meta:
        url_template = "/apis/schibsted.io/v1beta/namespaces/{namespace}/paasbetaapplications/{name}"
        watch_list_url = "/apis/schibsted.io/v1beta/watch/paasbetaapplications"

    # Workaround for https://github.com/kubernetes/kubernetes/issues/44182
    apiVersion = Field(six.text_type, "schibsted.io/v1beta")
    kind = Field(six.text_type, "PaasbetaApplication")

    metadata = Field(ObjectMeta)
    spec = Field(PaasbetaApplicationSpec)


class PaasbetaStatus(Model):
    class Meta:
        url_template = "/apis/schibsted.io/v1beta/namespaces/{namespace}/paasbetastatuses/{name}"

    # Workaround for https://github.com/kubernetes/kubernetes/issues/44182
    apiVersion = Field(six.text_type, "schibsted.io/v1beta")
    kind = Field(six.text_type, "PaasbetaStatus")

    metadata = Field(ObjectMeta)
    result = Field(six.text_type)
