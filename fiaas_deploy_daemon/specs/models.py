#!/usr/bin/env python
# -*- coding: utf-8

from collections import namedtuple


class AppSpec(namedtuple("AppSpec", [
        "namespace",
        "name",
        "image",
        "replicas",
        "autoscaler",
        "resources",
        "admin_access",
        "secrets_in_environment",
        "prometheus",
        "ports",
        "health_checks",
        "teams",
        "tags",
        "deployment_id",
        "labels",
        "annotations",
        "ingresses"])):

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
    "cpu_threshold_percentage"
])


LabelAndAnnotationSpec = namedtuple("LabelAndAnnotationSpec", [
  "deployment",
  "horizontal_pod_autoscaler",
  "ingress",
  "service"
])

IngressItemSpec = namedtuple("IngressItemSpec", [
    "host",
    "pathmappings",
])

IngressPathMappingSpec = namedtuple("IngressPathMappingSpec", [
    "path",
    "port",
])
