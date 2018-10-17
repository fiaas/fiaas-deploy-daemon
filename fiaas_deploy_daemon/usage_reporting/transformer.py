#!/usr/bin/env python
# -*- coding: utf-8

import collections
from datetime import datetime


def namedtuple_with_defaults(typename, field_names, default_values=()):
    T = collections.namedtuple(typename, field_names)
    T.__new__.__defaults__ = (None,) * len(T._fields)
    if isinstance(default_values, collections.Mapping):
        prototype = T(**default_values)
    else:
        prototype = T(*default_values)
    T.__new__.__defaults__ = tuple(prototype)
    return T


DevhoseDeploymentEvent = namedtuple_with_defaults('DevhoseDeploymentEvent',
                                                  'id application environment repository started_at timestamp target \
                                                   status source_type facility details trigger',
                                                  {'source_type': 'fiaas', 'facility': 'sdrn:schibsted:service:fiaas'})

status_map = {'STARTED': 'in_progress', 'SUCCESS': 'succeeded', 'FAILED': 'failed'}


class DevhoseDeploymentEventTransformer(object):
    def __init__(self, config):
        self._environment = config.environment
        self._target_infrastructure = config.usage_reporting_cluster_name
        self._target_provider = config.usage_reporting_provider_identifier
        self._deployments_started = {}

    def __call__(self, status, app_spec):
        if status == 'STARTED':
            started_timestamp = _timestamp()
            self._deployments_started[(app_spec.name, app_spec.deployment_id)] = started_timestamp
        else:
            started_timestamp = self._deployments_started.pop((app_spec.name, app_spec.deployment_id))
        event = DevhoseDeploymentEvent(id=app_spec.deployment_id,
                                       application=app_spec.name,
                                       environment=_environment(self._environment[:3]),
                                       repository=_repository(app_spec),
                                       started_at=started_timestamp,
                                       timestamp=started_timestamp if status == 'STARTED' else _timestamp(),
                                       target={'infrastructure': self._target_infrastructure,
                                               'provider': self._target_provider,
                                               'instance': app_spec.namespace},
                                       status=status_map[status],
                                       details={'environment': self._environment})
        return event.__dict__


def _environment(env):
    return env if env in ('dev', 'pre', 'pro',) else 'other'


def _timestamp():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _repository(app_spec):
    return app_spec.annotations.deployment.get("fiaas/source-repository")
