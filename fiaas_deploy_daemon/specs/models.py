#!/usr/bin/env python
# -*- coding: utf-8

from collections import namedtuple


class AppSpec(namedtuple("AppSpec", [
        "namespace",
        "name",
        "image",
        "replicas",
        "host",
        "resources",
        "admin_access",
        "has_secrets",
        "prometheus",
        "ports",
        "health_checks",
        "teams",
        "tags"])):

    __slots__ = ()

    @property
    def version(self):
        return self.image.split(":")[-1] if ":" in self.image else "<unknown>"

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
    "path"])

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
