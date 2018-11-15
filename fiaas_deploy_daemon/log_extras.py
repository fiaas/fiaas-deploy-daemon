#!/usr/bin/env python
# -*- coding: utf-8
import logging
import threading
from collections import defaultdict

_LOG_EXTRAS = threading.local()
LOGS = defaultdict(list)


class ExtraFilter(logging.Filter):
    def filter(self, record):
        record.extras = vars(_LOG_EXTRAS)
        return 1


def set_extras(app_spec=None, app_name=None, namespace=None, deployment_id=None):
    if app_spec:
        _LOG_EXTRAS.app_name = app_spec.name
        _LOG_EXTRAS.namespace = app_spec.namespace
        _LOG_EXTRAS.deployment_id = app_spec.deployment_id
    else:
        _LOG_EXTRAS.app_name = app_name
        _LOG_EXTRAS.namespace = namespace
        _LOG_EXTRAS.deployment_id = deployment_id


def get_running_logs(app_spec):
    key = (app_spec.name, app_spec.namespace, app_spec.deployment_id)
    return LOGS.get(key, [])


def get_final_logs(app_spec):
    key = (app_spec.name, app_spec.namespace, app_spec.deployment_id)
    return LOGS.pop(key, [])
