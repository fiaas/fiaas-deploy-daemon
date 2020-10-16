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


import collections
import pkgutil

import yaml

from ..factory import BaseTransformer, InvalidConfiguration
from ..lookup import LookupMapping

RESOURCE_UNDEFINED_UGLYHACK = object()
"""
This is a special value that the fields resources.{limits,requests}.{cpu,memory} can be set to to indicate to the
v3 AppSpec factory that the application should not have the default resource requirements set for the given field even
though that is the default behavior for FIAAS version 3.

This is neccessary because an application that is deployed using FIAAS v2 configuration but with no or partial
resources explicitly specified in its config will have the undefined fields set to the default value in for FIAAS v3
because the configuration is transparently transformed to that version.
This is unexpected behavior, so by setting the undefined fields to this value, the v3 AppSpec factory knows that it
should leave the fields unset and not apply the defaults.
"""


class Transformer(BaseTransformer):
    COPY_MAPPING = {
        # Old -> new
        ("prometheus",): ("metrics", "prometheus"),
        ("admin_access",): ("admin_access",),
    }

    def __init__(self):
        self._defaults = yaml.safe_load(pkgutil.get_data("fiaas_deploy_daemon.specs.v2", "defaults.yml"))

    def __call__(self, app_config, strip_defaults=False):
        lookup = LookupMapping(app_config, self._defaults)

        liveness = self._health_check(lookup["healthchecks"]["liveness"], lookup["ports"])
        if not lookup["healthchecks"].get_config_value("readiness") \
           and lookup["healthchecks"].get_config_value("liveness"):
            readiness = liveness
        else:
            readiness = self._health_check(lookup["healthchecks"]["readiness"], lookup["ports"])

        new_config = {
            'version': 3,
            'replicas': {
                'minimum': lookup["replicas"],
                'maximum': lookup["replicas"],
                'cpu_threshold_percentage': lookup["autoscaler"]["cpu_threshold_percentage"],
            },
            "healthchecks": {
                "liveness": liveness,
                "readiness": readiness,
            }
        }
        for old, new in list(Transformer.COPY_MAPPING.items()):
            value = _get(lookup, old)
            _set(new_config, new, value)
        if lookup["autoscaler"]["enabled"]:
            new_config["replicas"]["minimum"] = lookup["autoscaler"]["min_replicas"]

        new_config["resources"] = {}
        for requirement_type in ("limits", "requests"):
            new_config["resources"][requirement_type] = self._resource_requirement(lookup["resources"][requirement_type])

        new_config.update(self._ports(lookup["ports"], lookup["host"]))
        new_config = _flatten(new_config)
        if strip_defaults:
            new_config = self._strip_v3_defaults(new_config)
        return new_config

    def _strip_v3_defaults(self, app_config):
        v3defaults = yaml.safe_load(pkgutil.get_data("fiaas_deploy_daemon.specs.v3", "defaults.yml"))

        try:
            for requirement_type in ("limits", "requests"):
                for resource in ("cpu", "memory"):
                    if app_config["resources"][requirement_type][resource] == RESOURCE_UNDEFINED_UGLYHACK:
                        del app_config["resources"][requirement_type][resource]
            if not app_config['resources']:
                del app_config['resources']
        except KeyError:
            pass
        return dict(
            [("version", app_config["version"])] +
            list(_remove_intersect(app_config, v3defaults).items()))

    @staticmethod
    def _health_check(lookup, ports_lookup):
        value = {key: value for key, value in list(lookup.items()) if key not in ("execute", "http", "tcp")}
        for check in ("execute", "http", "tcp"):
            if lookup.get_config_value(check):
                value[check] = lookup[check]
                return value
        if len(ports_lookup) > 1:
            raise InvalidConfiguration("Must specify health check when more than one ports defined")
        elif ports_lookup[0]["protocol"] == "http":
            value["http"] = {
                "path": ports_lookup[0]["path"],
                "port": ports_lookup[0]["name"]
            }
        elif ports_lookup[0]["protocol"] == "tcp":
            value["tcp"] = {
                    "port": ports_lookup[0]["name"]
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

    @staticmethod
    def _resource_requirement(lookup):
        def get_config_value(lookup, key):
            value = lookup.get_config_value(key)
            return RESOURCE_UNDEFINED_UGLYHACK if value is None else value

        return {
            "cpu": get_config_value(lookup, "cpu"),
            "memory": get_config_value(lookup, "memory"),
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


def _flatten(d):
    if isinstance(d, collections.Mapping):
        return {k: _flatten(v) for k, v in list(d.items())}
    return d


def _remove_intersect(dict1, dict2):
    list(map(dict1.pop, [k for k in dict1 if k in dict2 and dict2[k] == dict1[k]]))
    keys_dict1 = set(dict1.keys())
    keys_dict2 = set(dict2.keys())
    for k in keys_dict1 & keys_dict2:
        if all(isinstance(x, collections.Mapping) for x in [dict1[k], dict2[k]]):
            dict1[k].update(_remove_intersect(dict1[k], dict2[k]))
        elif all(_single_dict_list(x) for x in [dict1[k], dict2[k]]):
            dict1[k] = [item for item in [_remove_intersect(x, y) for x, y in zip(dict1[k], dict2[k])] if item]
    list(map(dict1.pop, [k for k in dict1 if not dict1[k]]))
    return dict1


def _single_dict_list(x):
    return isinstance(x, collections.Sequence) and len(x) == 1 and isinstance(x[0], collections.Mapping)
