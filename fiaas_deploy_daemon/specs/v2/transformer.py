#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import, unicode_literals

import pkgutil

import yaml

from ..lookup import LookupMapping
from ..factory import BaseTransformer, InvalidConfiguration


class Transformer(BaseTransformer):
    COPY_MAPPING = {
        # Old -> new
        ("resources",): ("resources",),
        ("prometheus",): ("metrics", "prometheus"),
        ("admin_access",): ("admin_access",),
    }

    def __init__(self):
        self._defaults = yaml.safe_load(pkgutil.get_data("fiaas_deploy_daemon.specs.v2", "defaults.yml"))

    def __call__(self, app_config):
        lookup = LookupMapping(app_config, self._defaults)

        new_config = {
            'version': 3,
            'replicas': {
                'minimum': lookup["replicas"],
                'maximum': lookup["replicas"],
                'cpu_threshold_percentage': lookup["autoscaler"]["cpu_threshold_percentage"],
            },
            "healthchecks": {
                "liveness": self._health_check(lookup["healthchecks"]["liveness"], lookup["ports"]),
                "readiness": self._health_check(lookup["healthchecks"]["readiness"], lookup["ports"])
            }
        }
        for old, new in Transformer.COPY_MAPPING.iteritems():
            value = _get(lookup, old)
            _set(new_config, new, value)
        if lookup["autoscaler"]["enabled"]:
            new_config["replicas"]["minimum"] = lookup["autoscaler"]["min_replicas"]
        new_config.update(self._ports(lookup["ports"], lookup["host"]))
        return new_config

    @staticmethod
    def _health_check(lookup, ports_lookup):
        value = {key: value for key, value in lookup.iteritems() if key not in ("execute", "http", "tcp")}
        for check in ("execute", "http", "tcp"):
            if lookup.get_c_value(check):
                value[check] = lookup[check]
                return value
        if len(ports_lookup) > 1:
            raise InvalidConfiguration("Must specify health check when more than one ports defined")
        elif ports_lookup[0]["protocol"] == "http":
            value["http"] = {
                "path": ports_lookup[0]["path"],
                "port": ports_lookup[0]["port"]
            }
        elif ports_lookup[0]["protocol"] == "tcp":
            value["tcp"] = {
                    "port": ports_lookup[0]["port"]
                }
        return value

    @staticmethod
    def _ports(lookup, host):
        paths = []
        ports = []
        for port in lookup:
            if port["protocol"] == "http":
                paths.append({
                    "path": port["path"],
                    "port": port["name"]
                })
            ports.append({
                "protocol": port["protocol"],
                "name": port["name"],
                "port": port["port"],
                "target_port": port["target_port"]

            })
        return {
            "ingress": [{
                "host": host,
                "paths": paths
            }] if paths else [],
            "ports": ports
        }


def _get(d, keys):
    for k in keys:
        d = d[k]
    return d


def _set(d, keys, value):
    for k in keys[:-1]:
        if k not in d:
            d[k] = {}
        d = d[k]
    d[keys[-1]] = value
