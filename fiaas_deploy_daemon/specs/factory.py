#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import pkgutil

import yaml

from .models import AppSpec, ServiceSpec, ResourcesSpec, ResourceRequirementSpec, PrometheusSpec


class SpecFactory(object):
    def __init__(self, session):
        self._session = session
        self.default_app_config = yaml.safe_load(pkgutil.get_data("fiaas_deploy_daemon.specs", "defaults.yml"))
        self.default_service_config = self.default_app_config[u"services"][0]
        self.default_prometheus_config = self.default_app_config[u"prometheus"]

    def __call__(self, name, image, url):
        """Create an app_spec from the fiaas-config at the given URL"""
        resp = self._session.get(url, timeout=10)
        resp.raise_for_status()
        new_config = yaml.safe_load(resp.text)
        if u"service" in new_config and u"services" not in new_config:
            new_service_configs = [new_config[u"service"]]
        else:
            new_service_configs = self._get_app(u"services", new_config)
        service_specs = []
        for new_service_config in new_service_configs:
            service_specs.append(ServiceSpec(
                    self._get_service(u"exposed_port", new_service_config),
                    self._get_service(u"service_port", new_service_config),
                    self._get_service(u"type", new_service_config),
                    self._get_service(u"ingress", new_service_config),
                    self._get_service(u"readiness", new_service_config),
                    self._get_service(u"liveness", new_service_config),
                    self._get_service(u"probe_delay", new_service_config)
            ))
        admin_access = self._get_app(u"admin_access", new_config)
        has_secrets = self._get_app(u"has_secrets", new_config)

        resources = self._get_app(u"resources", new_config)
        resources_spec = ResourcesSpec(self._create_resource_requirement_spec(u"limits", resources),
                                       self._create_resource_requirement_spec(u"requests", resources))
        namespace = self._get_app(u"namespace", new_config)

        prom = self._get_app(u"prometheus", new_config)
        prometheus = self._create_prometheus_spec(u"enabled", prom)

        return AppSpec(namespace, name, image, service_specs, self._get_app(u"replicas", new_config),
                       resources_spec, admin_access, has_secrets, prometheus)

    def _get_app(self, field, primary):
        return self._get(field, primary, self.default_app_config)

    def _get_service(self, field, primary):
        return self._get(field, primary, self.default_service_config)

    def _get(self, field, primary, defaults):
        return primary.get(field, defaults[field])

    def _create_resource_requirement_spec(self, field, resources):
        return ResourceRequirementSpec(**resources.get(field, {}))

    def _create_prometheus_spec(self, field, prom):
        return PrometheusSpec(self._get(field, prom, self.default_prometheus_config))
