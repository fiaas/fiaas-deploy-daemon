#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import datetime
import json
import logging
import sys

from fiaas_deploy_daemon.log_extras import StatusHandler
from .log_extras import ExtraFilter


class FiaasFormatter(logging.Formatter):
    UNWANTED = (
        "msg", "args", "exc_info", "exc_text", "levelno", "created", "msecs", "relativeCreated", "funcName",
        "filename", "lineno", "module")
    RENAME = {
        "levelname": "level",
        "threadName": "thread",
        "name": "logger",
    }

    def format(self, record):
        fields = vars(record).copy()
        fields["@timestamp"] = self.format_time(record)
        fields["@version"] = 1
        fields["LocationInfo"] = self._build_location(fields)
        fields["message"] = record.getMessage()
        fields["extras"] = getattr(record, "extras", {})
        if "exc_info" in fields and fields["exc_info"]:
            fields["throwable"] = self.formatException(fields["exc_info"])
        for original, replacement in self.RENAME.iteritems():
            fields[replacement] = fields.pop(original)
        for unwanted in self.UNWANTED:
            fields.pop(unwanted)
        return json.dumps(fields, default=self._default_json_default)

    @staticmethod
    def format_time(record):
        """ELK is strict about it's timestamp, so use more strict ISO-format"""
        dt = datetime.datetime.fromtimestamp(record.created)
        return dt.isoformat()

    @staticmethod
    def _default_json_default(obj):
        """
        Coerce everything to strings.
        All objects representing time get output as ISO8601.
        """
        if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
            return obj.isoformat()
        else:
            return str(obj)

    @staticmethod
    def _build_location(fields):
        return {
            "method": fields["funcName"],
            "file": fields["filename"],
            "line": fields["lineno"],
            "module": fields["module"]
        }


def init_logging(config):
    """Set up logging system, according to FINN best practice for cloud

    - Always logs to stdout
    - Select format from env-variable LOG_FORMAT
    -- json - Use the logstash formatter to output json
    -- plain or blank - Use plain formatting
    -- Anything else raises exception
    """
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(ExtraFilter())
    if _json_format(config):
        handler.setFormatter(FiaasFormatter())
    elif _plain_format(config):
        handler.setFormatter(logging.Formatter("[%(asctime)s|%(levelname)7s] %(message)s [%(name)s|%(threadName)s]"))
    if config.debug:
        root.setLevel(logging.DEBUG)
    root.addHandler(handler)
    root.addHandler(StatusHandler())
    _set_special_levels()


def _set_special_levels():
    logging.getLogger("werkzeug").setLevel(logging.WARN)
    # Kafka is really noisy...
    kafka_logger = logging.getLogger("kafka")
    if kafka_logger.getEffectiveLevel() < logging.INFO:
        kafka_logger.setLevel(logging.INFO)


def _json_format(config):
    return config.log_format == "json"


def _plain_format(config):
    return config.log_format == "plain"
