#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import pkgutil

import yaml
from .. import InvalidConfiguration
from ..models import AppSpec, PrometheusSpec, ResourcesSpec, ResourceRequirementSpec, PortSpec, HealthCheckSpec, CheckSpec, \
    HttpCheckSpec, TcpCheckSpec, ExecCheckSpec
from .lookup import LookupMapping


class Factory(object):
    def __init__(self):
        self._defaults = yaml.safe_load(pkgutil.get_data("fiaas_deploy_daemon.specs.v2", "defaults.yml"))

    def __call__(self, name, image, app_config):
        lookup = LookupMapping(app_config, self._defaults)
        ports = self._ports(lookup[u"ports"])
        return AppSpec(
            lookup[u"namespace"],
            name,
            image,
            lookup[u"replicas"],
            lookup[u"host"],
            self._resources_spec(lookup[u"resources"]),
            lookup[u"admin_access"],
            lookup[u"has_secrets"],
            self._prometheus_spec(lookup[u"prometheus"]),
            ports,
            self._health_checks_spec(lookup[u"healthchecks"], ports))

    @staticmethod
    def _prometheus_spec(lookup):
        return PrometheusSpec(lookup[u"enabled"], lookup[u"port"], lookup[u"path"])

    def _resources_spec(self, lookup):
        return ResourcesSpec(
            self._resource_requirements_spec(lookup[u"limits"]),
            self._resource_requirements_spec(lookup[u"requests"])
        )

    @staticmethod
    def _resource_requirements_spec(lookup):
        return ResourceRequirementSpec(lookup[u"cpu"], lookup[u"memory"])

    @staticmethod
    def _ports(lookup):
        return [PortSpec(
            l[u"protocol"],
            l[u"name"],
            l[u"port"],
            l[u"target_port"],
            l[u"path"]) for l in lookup]

    def _health_checks_spec(self, lookup, ports):
        return HealthCheckSpec(
            self._check_spec(lookup[u"liveness"], ports),
            self._check_spec(lookup[u"readiness"], ports)
        )

    def _check_spec(self, lookup, ports):
        first_port = ports[0]
        exec_check_spec = http_check_spec = tcp_check_spec = None
        if lookup.get_c_value(u"execute"):
            exec_check_spec = self._exec_check_spec(lookup[u"execute"])
        elif lookup.get_c_value(u"http"):
            http_check_spec = self._http_check_spec(lookup[u"http"], first_port)
        elif lookup.get_c_value(u"tcp"):
            tcp_check_spec = self._tcp_check_spec(lookup[u"tcp"], first_port)
        elif len(ports) > 1:
            raise InvalidConfiguration("Must specify health check when more than one ports defined")
        elif first_port.protocol == u"http":
            http_check_spec = self._http_check_spec(lookup[u"http"], first_port)
        elif first_port.protocol == u"tcp":
            tcp_check_spec = self._tcp_check_spec(lookup[u"tcp"], first_port)
        return CheckSpec(
            exec_check_spec,
            http_check_spec,
            tcp_check_spec,
            lookup[u"initial_delay_seconds"],
            lookup[u"period_seconds"],
            lookup[u"success_threshold"],
            lookup[u"timeout_seconds"]
        )

    @staticmethod
    def _http_check_spec(lookup, first_port):
        if lookup.get_c_value(u"port"):
            port = lookup[u"port"]
        else:
            port = first_port.name
        if lookup.get_c_value(u"path"):
            path = lookup[u"path"]
        else:
            path = first_port.path
        return HttpCheckSpec(
            path,
            port,
            lookup[u"http_headers"].raw(),
        )

    @staticmethod
    def _tcp_check_spec(lookup, first_port):
        if lookup.get_c_value(u"port"):
            port = lookup[u"port"]
        else:
            port = first_port.port
        return TcpCheckSpec(port)

    @staticmethod
    def _exec_check_spec(lookup):
        return ExecCheckSpec(lookup[u"command"])
