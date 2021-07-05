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
from __future__ import absolute_import, unicode_literals

import pkgutil

import yaml

from ..factory import BaseFactory, InvalidConfiguration
from ..lookup import LookupMapping
from ..models import AppSpec, PrometheusSpec, DatadogSpec, ResourcesSpec, ResourceRequirementSpec, PortSpec, \
    HealthCheckSpec, CheckSpec, HttpCheckSpec, TcpCheckSpec, ExecCheckSpec, AutoscalerSpec, \
    LabelAndAnnotationSpec, IngressItemSpec, IngressPathMappingSpec, StrongboxSpec, IngressTlsSpec, SecretsSpec
from ..v2.transformer import RESOURCE_UNDEFINED_UGLYHACK
from ...tools import merge_dicts


class Factory(BaseFactory):
    version = 3

    def __init__(self, config=None):
        self._defaults = yaml.safe_load(pkgutil.get_data("fiaas_deploy_daemon.specs.v3", "defaults.yml"))
        # Overwrite default value based on config flag for ingress_tls
        self._defaults["extensions"]["tls"]["enabled"] = config and config.use_ingress_tls == "default_on"

    def __call__(self, uid, name, image, teams, tags, app_config, deployment_id, namespace,
                 additional_labels, additional_annotations):
        if app_config.get("extensions") and app_config["extensions"].get("tls") and type(
                app_config["extensions"]["tls"]) == bool:
            app_config["extensions"]["tls"] = {u"enabled": app_config["extensions"]["tls"]}
        lookup = LookupMapping(config=app_config, defaults=self._defaults)
        app_spec = AppSpec(
            uid=uid,
            namespace=namespace,
            name=name,
            image=image,
            autoscaler=self._autoscaler_spec(lookup["replicas"]),
            resources=self._resources_spec(lookup["resources"]),
            admin_access=lookup["admin_access"],
            secrets_in_environment=lookup["secrets_in_environment"],
            prometheus=self._prometheus_spec(lookup["metrics"]["prometheus"]),
            datadog=self._datadog_spec(lookup["metrics"]["datadog"]),
            ports=self._port_specs(lookup["ports"]),
            health_checks=self._health_checks_spec(lookup["healthchecks"], lookup["ports"]),
            teams=teams,
            tags=tags,
            deployment_id=deployment_id,
            labels=self._labels_annotations_spec(lookup["labels"], additional_labels),
            annotations=self._labels_annotations_spec(lookup["annotations"], additional_annotations),
            ingresses=self._ingress_items(lookup["ingress"], lookup["ports"]),
            strongbox=self._strongbox(lookup["extensions"]["strongbox"]),
            singleton=lookup["replicas"]["singleton"],
            ingress_tls=IngressTlsSpec(enabled=lookup["extensions"]["tls"]["enabled"],
                                       certificate_issuer=lookup["extensions"]["tls"]["certificate_issuer"]),
            secrets=self._secrets_specs(lookup["extensions"]["secrets"]),
            hooks=lookup["extensions"]["hooks"],
            app=app_config
        )
        return app_spec

    @staticmethod
    def _autoscaler_spec(replicas_lookup):
        minimum = replicas_lookup["minimum"]
        maximum = replicas_lookup["maximum"]
        enabled = minimum != maximum
        cpu_threshold_percentage = replicas_lookup["cpu_threshold_percentage"]
        return AutoscalerSpec(
            enabled=enabled,
            min_replicas=minimum,
            max_replicas=maximum,
            cpu_threshold_percentage=cpu_threshold_percentage
        )

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
    def _datadog_spec(datadog_lookup):
        return DatadogSpec(
            enabled=datadog_lookup["enabled"],
            tags=dict(datadog_lookup["tags"])
        )

    @staticmethod
    def _port_specs(ports_lookup):
        return [PortSpec(protocol=port["protocol"],
                         name=port["name"],
                         port=port["port"],
                         target_port=port["target_port"])
                for port in ports_lookup]

    def _health_checks_spec(self, healthchecks_lookup, ports_lookup):
        liveness = self._check_spec(healthchecks_lookup["liveness"], ports_lookup, "liveness")
        if not healthchecks_lookup.get_config_value("readiness") and healthchecks_lookup.get_config_value("liveness"):
            readiness = liveness
        else:
            readiness = self._check_spec(healthchecks_lookup["readiness"], ports_lookup, "readiness")
        return HealthCheckSpec(liveness, readiness)

    def _check_spec(self, healthcheck_lookup, ports_lookup, check_type):
        first_port_lookup = ports_lookup[0] if ports_lookup else None
        exec_check_spec = http_check_spec = tcp_check_spec = None
        if healthcheck_lookup.get_config_value("execute"):
            exec_check_spec = self._exec_check_spec(healthcheck_lookup["execute"])
        elif healthcheck_lookup.get_config_value("http"):
            http_check_spec = self._http_check_spec(healthcheck_lookup["http"], first_port_lookup, check_type)
        elif healthcheck_lookup.get_config_value("tcp"):
            tcp_check_spec = self._tcp_check_spec(healthcheck_lookup["tcp"], first_port_lookup, check_type)
        elif len(ports_lookup) != 1:
            raise InvalidConfiguration("Must specify {} check or exactly one port".format(check_type))
        elif first_port_lookup["protocol"] == "http":
            http_check_spec = self._http_check_spec(healthcheck_lookup["http"], first_port_lookup, check_type)
        elif first_port_lookup["protocol"] == "tcp":
            tcp_check_spec = self._tcp_check_spec(healthcheck_lookup["tcp"], first_port_lookup, check_type)

        return CheckSpec(
            exec_check_spec,
            http_check_spec,
            tcp_check_spec,
            healthcheck_lookup["initial_delay_seconds"],
            healthcheck_lookup["period_seconds"],
            healthcheck_lookup["success_threshold"],
            healthcheck_lookup["failure_threshold"],
            healthcheck_lookup["timeout_seconds"]
        )

    @staticmethod
    def _http_check_spec(check_lookup, first_port_lookup, check_type):
        if check_lookup.get_config_value("port"):
            port = check_lookup["port"]
        elif first_port_lookup:
            port = first_port_lookup["name"]
        else:
            raise InvalidConfiguration("Unable to determine port to use for http {} check".format(check_type))
        return HttpCheckSpec(
            path=check_lookup["path"],
            port=port,
            http_headers=check_lookup["http_headers"].raw(),
        )

    @staticmethod
    def _tcp_check_spec(check_lookup, first_port_lookup, check_type):
        if check_lookup.get_config_value("port"):
            port = check_lookup["port"]
        elif first_port_lookup:
            port = first_port_lookup["name"]
        else:
            raise InvalidConfiguration("Unable to determine port to use for tcp {} check".format(check_type))
        return TcpCheckSpec(port=port)

    @staticmethod
    def _exec_check_spec(check_lookup):
        return ExecCheckSpec(command=check_lookup["command"])

    @staticmethod
    def _labels_annotations_spec(labels_annotations_lookup, overrides):
        params = {
            'deployment': dict(labels_annotations_lookup["deployment"]),
            'horizontal_pod_autoscaler': dict(labels_annotations_lookup["horizontal_pod_autoscaler"]),
            'ingress': dict(labels_annotations_lookup["ingress"]),
            'service': dict(labels_annotations_lookup["service"]),
            'pod': dict(labels_annotations_lookup["pod"]),
            'status': {}
        }
        if overrides:
            globals = _get_value("_global", overrides)
            for key in LabelAndAnnotationSpec._fields:
                override = _get_value(key, overrides)
                params[key] = merge_dicts(params.get(key, {}), globals, override)
        return LabelAndAnnotationSpec(**params)

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

        def ingress_item(host, paths, annotations):
            ingress_path_mapping_specs = [
                IngressPathMappingSpec(path=pathmapping["path"], port=resolve_port_number(pathmapping["port"]))
                for pathmapping in paths
            ]
            return IngressItemSpec(host=host, pathmappings=ingress_path_mapping_specs, annotations=annotations)

        if len(http_ports.items()) > 0:
            return [ingress_item(host_path_mapping["host"], host_path_mapping["paths"], host_path_mapping["annotations"])
                    for host_path_mapping in ingress_lookup]
        else:
            return []

    @staticmethod
    def _strongbox(strongbox_lookup):
        iam_role = strongbox_lookup.get_config_value("iam_role")
        groups = strongbox_lookup.get_config_value("groups")
        enabled = iam_role is not None and groups is not None
        return StrongboxSpec(enabled=enabled, iam_role=iam_role,
                             aws_region=strongbox_lookup["aws_region"],
                             groups=groups)

    @staticmethod
    def _secrets_specs(secrets_lookup):
        return [SecretsSpec(type=k,
                            parameters=v["parameters"],
                            annotations=v["annotations"]) for (k, v) in secrets_lookup.iteritems()]


def _get_value(key, overrides):
    override = getattr(overrides, key)
    if override is None:
        override = {}
    return override
