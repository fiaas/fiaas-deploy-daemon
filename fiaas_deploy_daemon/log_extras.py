#!/usr/bin/env python
# -*- coding: utf-8
import logging
import threading
from collections import defaultdict

_LOGS = defaultdict(list)
_LOG_EXTRAS = threading.local()
_LOG_FORMAT = u"[%(asctime)s|%(levelname)7s] %(message)s " \
              u"[%(name)s|%(threadName)s|%(extras_namespace)s/%(extras_app_name)s]"


class ExtraFilter(logging.Filter):
    def filter(self, record):
        extras = {}
        for key in ("app_name", "namespace", "deployment_id"):
            extras[key] = getattr(_LOG_EXTRAS, key, "")
        record.extras = extras
        return 1


class StatusFormatter(logging.Formatter):
    def __init__(self):
        super(StatusFormatter, self).__init__(_LOG_FORMAT, None)

    def format(self, record):
        record = self._flatten_extras(record)
        return super(StatusFormatter, self).format(record)

    @staticmethod
    def _flatten_extras(record):
        for key in record.extras:
            flat_key = "extras_{}".format(key)
            setattr(record, flat_key, record.extras[key])
        return record


class StatusHandler(logging.Handler):
    def __init__(self):
        super(StatusHandler, self).__init__(logging.INFO)
        self.addFilter(ExtraFilter())
        self.setFormatter(StatusFormatter())

    def emit(self, record):
        append_log(record, self.format(record))


def set_extras(app_spec=None, app_name=None, namespace=None, deployment_id=None):
    if app_spec:
        app_name = app_spec.name
        namespace = app_spec.namespace
        deployment_id = app_spec.deployment_id
    if any(x is None for x in (app_name, namespace, deployment_id)):
        raise TypeError("Either app_spec, or all of (app_name, namespace, deployment_id) must be specified")
    _LOG_EXTRAS.app_name = app_name
    _LOG_EXTRAS.namespace = namespace
    _LOG_EXTRAS.deployment_id = deployment_id
    _LOG_EXTRAS.is_set = True


def get_running_logs(app_spec):
    key = (app_spec.name, app_spec.namespace, app_spec.deployment_id)
    return _LOGS.get(key, [])


def get_final_logs(app_spec):
    key = (app_spec.name, app_spec.namespace, app_spec.deployment_id)
    return _LOGS.pop(key, [])


def append_log(record, message):
    if hasattr(record, "extras"):
        key = (record.extras.get("app_name"), record.extras.get("namespace"), record.extras.get("deployment_id"))
        _LOGS[key].append(message)
