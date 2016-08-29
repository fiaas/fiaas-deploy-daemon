#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import pkgutil

import yaml

from ..models import AppSpec, ResourceRequirementSpec, ResourcesSpec, PrometheusSpec, PortSpec, HealthCheckSpec, HttpCheckSpec, \
    TcpCheckSpec, CheckSpec


class Factory(object):
    def __init__(self):
        self.default_app_config = yaml.safe_load(pkgutil.get_data("fiaas_deploy_daemon.specs.v1", "defaults.yml"))
        self.default_service_config = self.default_app_config[u"services"][0]
        self.default_prometheus_config = self.default_app_config[u"prometheus"]

    def __call__(self, name, image, app_config):
        if u"service" in app_config and u"services" not in app_config:
            new_service_configs = [app_config[u"service"]]
        else:
            new_service_configs = self._get_app(u"services", app_config)
        ports = []
        health_checks = []
        for new_service_config in new_service_configs:
            port = self._create_port(new_service_config)
            ports.append(port)
            health_checks.append(self._create_health_checks(port.protocol, new_service_config))
        admin_access = self._get_app(u"admin_access", app_config)
        has_secrets = self._get_app(u"has_secrets", app_config)

        resources = self._get_app(u"resources", app_config)
        resources_spec = ResourcesSpec(self._create_resource_requirement_spec(u"limits", resources),
                                       self._create_resource_requirement_spec(u"requests", resources))
        namespace = self._get_app(u"namespace", app_config)

        prom = self._get_app(u"prometheus", app_config)
        prometheus = self._create_prometheus_spec(prom, ports)

        return AppSpec(namespace, name, image, self._get_app(u"replicas", app_config),
                       None, resources_spec, admin_access, has_secrets, prometheus, ports, health_checks[0])

    def _create_port(self, service_config):
        protocol = self._get_service(u"type", service_config)
        if protocol == u"thrift":
            protocol = u"tcp"
        service_port = self._get_service(u"service_port", service_config)
        exposed_port = self._get_service(u"exposed_port", service_config)
        name = "{}{}".format(protocol, exposed_port)
        return PortSpec(protocol, name, service_port, exposed_port, self._get_service(u"ingress", service_config))

    def _create_health_checks(self, protocol, service_config):
        liveness = self._create_check(protocol, service_config, u"liveness")
        readiness = self._create_check(protocol, service_config, u"readiness")
        return HealthCheckSpec(liveness, readiness)

    def _create_check(self, protocol, service_config, check_type):
        exposed_port = self._get_service(u"exposed_port", service_config)
        probe_delay = self._get_service(u"probe_delay", service_config)
        port = "{}{}".format(protocol, exposed_port)
        http_check = tcp_check = None
        if protocol == u"http":
            path = self._get_service(check_type, service_config)
            http_check = HttpCheckSpec(path, port, {})
        else:
            tcp_check = TcpCheckSpec(port)
        return CheckSpec(None, http_check, tcp_check, probe_delay, 10, 1, 1)

    def _get_app(self, field, primary):
        return self._get(field, primary, self.default_app_config)

    def _get_service(self, field, primary):
        return self._get(field, primary, self.default_service_config)

    def _get(self, field, primary, defaults):
        return primary.get(field, defaults[field])

    def _create_prometheus_spec(self, prom, ports):
        enabled = self._get(u"enabled", prom, self.default_prometheus_config)
        port = None
        if enabled:
            port_specs = [ps for ps in ports if ps.protocol == u"http"]
            if port_specs:
                port = port_specs[0].name
        return PrometheusSpec(enabled, port, u"/internal-backstage/prometheus")

    @staticmethod
    def _create_resource_requirement_spec(field, resources):
        config = resources.get(field, {})
        return ResourceRequirementSpec(config.get(u"cpu"), config.get(u"memory"))
