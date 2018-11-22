#!/usr/bin/env python
# -*- coding: utf-8
import logging
import sys
import threading
from collections import defaultdict

_LOGS = defaultdict(list)
_LOG_EXTRAS = threading.local()
_LOG_FORMAT = u"[{asctime}|{levelname:7}] {message} [{name}|{threadName}|{extras[namespace]}/{extras[app_name]}]"


class ExtraFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(_LOG_EXTRAS, "is_set"):
            set_extras()
        record.extras = vars(_LOG_EXTRAS)
        return 1


class StatusFormatter(logging.Formatter):
    def __init__(self):
        super(StatusFormatter, self).__init__(_LOG_FORMAT, None)

    def format(self, record):
        """Copied from base class, and changed to use .format instead of %"""
        record.message = record.getMessage()
        if self.usesTime():
            record.asctime = self.formatTime(record, self.datefmt)
        try:
            s = self._fmt.format(**record.__dict__)
        except UnicodeDecodeError as e:
            try:
                record.name = record.name.decode('utf-8')
                s = self._fmt.format(**record.__dict__)
            except UnicodeDecodeError:
                raise e
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            if s[-1:] != "\n":
                s = s + "\n"
            try:
                s = s + record.exc_text
            except UnicodeError:
                s = s + record.exc_text.decode(sys.getfilesystemencoding(), 'replace')
        return s

    def usesTime(self):
        return "asctime" in self._fmt


class StatusHandler(logging.Handler):
    def __init__(self):
        super(StatusHandler, self).__init__(logging.WARNING)
        self.addFilter(ExtraFilter())
        self.setFormatter(StatusFormatter())

    def emit(self, record):
        append_log(record, self.format(record))


def set_extras(app_spec=None, app_name=None, namespace=None, deployment_id=None):
    _LOG_EXTRAS.is_set = True
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
    return _LOGS.get(key, [])


def get_final_logs(app_spec):
    key = (app_spec.name, app_spec.namespace, app_spec.deployment_id)
    return _LOGS.pop(key, [])


def append_log(record, message):
    if hasattr(record, "extras"):
        key = (record.extras.get("app_name"), record.extras.get("namespace"), record.extras.get("deployment_id"))
        _LOGS[key].append(message)
