#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import pkgutil

import yaml

from ..lookup import LookupMapping
from ..factory import InvalidConfiguration
from ..models import AppSpec, PrometheusSpec, ResourcesSpec, ResourceRequirementSpec, PortSpec, HealthCheckSpec, \
    CheckSpec, HttpCheckSpec, TcpCheckSpec, ExecCheckSpec, AutoscalerSpec, LabelAndAnnotationSpec, IngressItemSpec, \
    IngressPathMappingSpec


class Factory(object):
    version = 2

    def __init__(self):
        self._defaults = yaml.safe_load(pkgutil.get_data("fiaas_deploy_daemon.specs.v2", "defaults.yml"))

    def __call__(self, name, image, teams, tags, app_config, deployment_id):
        lookup = LookupMapping(app_config, self._defaults)
        return AppSpec(
            lookup[u"namespace"],
            name,
            image,
            lookup[u"replicas"],
            self._autoscaler_spec(lookup[u"autoscaler"]),
            self._resources_spec(lookup[u"resources"]),
            lookup[u"admin_access"],
            False,
            self._prometheus_spec(lookup[u"prometheus"]),
            self._ports(lookup[u"ports"]),
            self._health_checks_spec(lookup[u"healthchecks"], lookup[u"ports"]),
            teams,
            tags,
            deployment_id,
            LabelAndAnnotationSpec({}, {}, {}, {}),
            LabelAndAnnotationSpec({}, {}, {}, {}),
            self._ingress_items(lookup)
        )

    @staticmethod
    def _ingress_items(lookup):
        host = lookup[u"host"]
        pathmappings = [IngressPathMappingSpec(path=port[u"path"], port=port[u"port"])
                        for port in lookup[u"ports"]
                        if port[u"protocol"] == u"http"]
        if len(pathmappings) > 0:
            return [IngressItemSpec(host=host, pathmappings=pathmappings)]
        else:
            return []

    @staticmethod
    def _autoscaler_spec(lookup):
        return AutoscalerSpec(lookup[u"enabled"], lookup[u"min_replicas"], lookup[u"cpu_threshold_percentage"])

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
            l[u"target_port"]) for l in lookup]

    def _health_checks_spec(self, lookup, ports_lookup):
        liveness = self._check_spec(lookup[u"liveness"], ports_lookup)
        if not lookup.get_c_value(u"readiness"):
            readiness = liveness
        else:
            readiness = self._check_spec(lookup[u"readiness"], ports_lookup)
        return HealthCheckSpec(liveness, readiness)

    def _check_spec(self, lookup, ports_lookup):
        first_port_lookup = ports_lookup[0]
        exec_check_spec = http_check_spec = tcp_check_spec = None
        if lookup.get_c_value(u"execute"):
            exec_check_spec = self._exec_check_spec(lookup[u"execute"])
        elif lookup.get_c_value(u"http"):
            http_check_spec = self._http_check_spec(lookup[u"http"], first_port_lookup)
        elif lookup.get_c_value(u"tcp"):
            tcp_check_spec = self._tcp_check_spec(lookup[u"tcp"], first_port_lookup)
        elif len(ports_lookup) > 1:
            raise InvalidConfiguration("Must specify health check when more than one ports defined")
        elif first_port_lookup[u"protocol"] == u"http":
            http_check_spec = self._http_check_spec(lookup[u"http"], first_port_lookup)
        elif first_port_lookup[u"protocol"] == u"tcp":
            tcp_check_spec = self._tcp_check_spec(lookup[u"tcp"], first_port_lookup)
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
    def _http_check_spec(lookup, first_port_lookup):
        if lookup.get_c_value(u"port"):
            port = lookup[u"port"]
        else:
            port = first_port_lookup[u"name"]
        if lookup.get_c_value(u"path"):
            path = lookup[u"path"]
        else:
            path = first_port_lookup[u"path"]
        return HttpCheckSpec(
            path,
            port,
            lookup[u"http_headers"].raw(),
        )

    @staticmethod
    def _tcp_check_spec(lookup, first_port_lookup):
        if lookup.get_c_value(u"port"):
            port = lookup[u"port"]
        else:
            port = first_port_lookup[u"port"]
        return TcpCheckSpec(port)

    @staticmethod
    def _exec_check_spec(lookup):
        return ExecCheckSpec(lookup[u"command"])
