#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import, unicode_literals

import pkgutil

import yaml

from ..lookup import LookupMapping
from ..factory import BaseFactory, InvalidConfiguration
from ..models import AppSpec, PrometheusSpec, ResourcesSpec, ResourceRequirementSpec, PortSpec, HealthCheckSpec, \
    CheckSpec, HttpCheckSpec, TcpCheckSpec, ExecCheckSpec, AutoscalerSpec, LabelAndAnnotationSpec, IngressItemSpec, \
    IngressPathMappingSpec
from ..v2.transformer import RESOURCE_UNDEFINED_UGLYHACK


class Factory(BaseFactory):

    version = 3

    def __init__(self):
        self._defaults = yaml.safe_load(pkgutil.get_data("fiaas_deploy_daemon.specs.v3", "defaults.yml"))

    def __call__(self, name, image, teams, tags, app_config, deployment_id, namespace):
        lookup = LookupMapping(config=app_config, defaults=self._defaults)
        app_spec = AppSpec(
            namespace=namespace,
            name=name,
            image=image,
            replicas=lookup["replicas"]["maximum"],
            autoscaler=self._autoscaler_spec(lookup["replicas"]),
            resources=self._resources_spec(lookup["resources"]),
            admin_access=lookup["admin_access"],
            secrets_in_environment=lookup["secrets_in_environment"],
            prometheus=self._prometheus_spec(lookup["metrics"]["prometheus"]),
            datadog=lookup["metrics"]["datadog"]["enabled"],
            ports=self._port_specs(lookup["ports"]),
            health_checks=self._health_checks_spec(lookup["healthchecks"], lookup["ports"]),
            teams=teams,
            tags=tags,
            deployment_id=deployment_id,
            labels=self._labels_annotations_spec(lookup["labels"]),
            annotations=self._labels_annotations_spec(lookup["annotations"]),
            ingresses=self._ingress_items(lookup["ingress"], lookup["ports"])
        )
        return app_spec

    @staticmethod
    def _autoscaler_spec(replicas_lookup):
        minimum = replicas_lookup["minimum"]
        maximum = replicas_lookup["maximum"]
        enabled = minimum != maximum
        cpu_threshold_percentage = replicas_lookup["cpu_threshold_percentage"]
        return AutoscalerSpec(enabled=enabled, min_replicas=minimum, cpu_threshold_percentage=cpu_threshold_percentage)

    def _resources_spec(self, resources_lookup):
        return ResourcesSpec(
            limits=self._resource_requirements_spec(resources_lookup["limits"]),
            requests=self._resource_requirements_spec(resources_lookup["requests"])
        )

    @staticmethod
    def _resource_requirements_spec(resource_lookup):
        cpu = None if resource_lookup["cpu"] == RESOURCE_UNDEFINED_UGLYHACK else resource_lookup["cpu"]
        memory = None if resource_lookup["memory"] == RESOURCE_UNDEFINED_UGLYHACK else resource_lookup["memory"]
        return ResourceRequirementSpec(cpu=cpu, memory=memory)

    @staticmethod
    def _prometheus_spec(prometheus_lookup):
        return PrometheusSpec(
            enabled=prometheus_lookup["enabled"],
            port=prometheus_lookup["port"],
            path=prometheus_lookup["path"]
        )

    @staticmethod
    def _port_specs(ports_lookup):
        return [PortSpec(protocol=port["protocol"],
                         name=port["name"],
                         port=port["port"],
                         target_port=port["target_port"])
                for port in ports_lookup]

    def _health_checks_spec(self, healthchecks_lookup, ports_lookup):
        liveness = self._check_spec(healthchecks_lookup["liveness"], ports_lookup)
        if not healthchecks_lookup.get_config_value("readiness") and healthchecks_lookup.get_config_value("liveness"):
            readiness = liveness
        else:
            readiness = self._check_spec(healthchecks_lookup["readiness"], ports_lookup)
        return HealthCheckSpec(liveness, readiness)

    def _check_spec(self, healthcheck_lookup, ports_lookup):
        first_port_lookup = ports_lookup[0]
        exec_check_spec = http_check_spec = tcp_check_spec = None
        if healthcheck_lookup.get_config_value("execute"):
            exec_check_spec = self._exec_check_spec(healthcheck_lookup["execute"])
        elif healthcheck_lookup.get_config_value("http"):
            http_check_spec = self._http_check_spec(healthcheck_lookup["http"], first_port_lookup)
        elif healthcheck_lookup.get_config_value("tcp"):
            tcp_check_spec = self._tcp_check_spec(healthcheck_lookup["tcp"], first_port_lookup)
        elif len(ports_lookup) > 1:
            raise InvalidConfiguration("Must specify health check when more than one ports defined")
        elif first_port_lookup["protocol"] == "http":
            http_check_spec = self._http_check_spec(healthcheck_lookup["http"], first_port_lookup)
        elif first_port_lookup["protocol"] == "tcp":
            tcp_check_spec = self._tcp_check_spec(healthcheck_lookup["tcp"], first_port_lookup)

        return CheckSpec(
            exec_check_spec,
            http_check_spec,
            tcp_check_spec,
            healthcheck_lookup["initial_delay_seconds"],
            healthcheck_lookup["period_seconds"],
            healthcheck_lookup["success_threshold"],
            healthcheck_lookup["timeout_seconds"]
        )

    @staticmethod
    def _http_check_spec(check_lookup, first_port_lookup):
        if check_lookup.get_config_value("port"):
            port = check_lookup["port"]
        else:
            port = first_port_lookup["name"]
        return HttpCheckSpec(
            path=check_lookup["path"],
            port=port,
            http_headers=check_lookup["http_headers"].raw(),
        )

    @staticmethod
    def _tcp_check_spec(check_lookup, first_port_lookup):
        if check_lookup.get_config_value("port"):
            port = check_lookup["port"]
        else:
            port = first_port_lookup["name"]
        return TcpCheckSpec(port=port)

    @staticmethod
    def _exec_check_spec(check_lookup):
        return ExecCheckSpec(command=check_lookup["command"])

    @staticmethod
    def _labels_annotations_spec(labels_annotations_lookup):
        return LabelAndAnnotationSpec(
            deployment=dict(labels_annotations_lookup["deployment"]),
            horizontal_pod_autoscaler=dict(labels_annotations_lookup["horizontal_pod_autoscaler"]),
            ingress=dict(labels_annotations_lookup["ingress"]),
            service=dict(labels_annotations_lookup["service"])
        )

    @staticmethod
    def _ingress_items(ingress_lookup, ports_lookup):
        http_ports = {port["name"]: port["port"] for port in ports_lookup if port["protocol"] == "http"}

        def resolve_port_number(port):
            port_number = http_ports.get(port)
            if port_number:
                return port_number
            elif port in http_ports.values():
                return port
            else:
                raise InvalidConfiguration("{} is not a valid port name or port number".format(port))

        def ingress_item(host, paths):
            ingress_path_mapping_specs = [
                IngressPathMappingSpec(path=pathmapping["path"], port=resolve_port_number(pathmapping["port"]))
                for pathmapping in paths
            ]
            return IngressItemSpec(host=host, pathmappings=ingress_path_mapping_specs)

        if len(http_ports.items()) > 0:
            return [ingress_item(host_path_mapping["host"], host_path_mapping["paths"])
                    for host_path_mapping in ingress_lookup]
        else:
            return []
