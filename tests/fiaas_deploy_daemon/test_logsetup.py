#!/usr/bin/env python
# -*- coding: utf-8
import json
import logging
import sys
from cStringIO import StringIO

from fiaas_deploy_daemon.log_extras import StatusHandler, ExtraFilter, set_extras
from fiaas_deploy_daemon.logsetup import init_logging, FiaasFormatter

TEST_MESSAGE = "This is a test log message"


class TestLogSetup(object):
    def setup(self):
        self.root = logging.getLogger()

    def teardown(self):
        handlers = list(self.root.handlers)
        for handler in handlers:
            self.root.removeHandler(handler)

    def assert_stream_handler(self, handler):
        assert isinstance(handler, logging.StreamHandler), "Handler is not a StreamHandler"
        assert handler.stream == sys.stdout, "Not streaming to stdout"
        assert isinstance(handler.filters[0], ExtraFilter)

    def assert_status_handler(self, handler):
        assert isinstance(handler, StatusHandler), "Handler is not a StatusHandler"
        assert isinstance(handler.filters[0], ExtraFilter)

    def test_default_behaviour(self):
        init_logging(_FakeConfig())

        assert len(self.root.handlers) == 2, "Wrong number of handlers defined"
        stream_handler = self.root.handlers[0]
        self.assert_stream_handler(stream_handler)
        status_handler = self.root.handlers[-1]
        self.assert_status_handler(status_handler)
        assert isinstance(stream_handler.formatter, logging.Formatter), "Should use standard formatter"
        assert self.root.level == logging.INFO

    def test_output_json(self):
        init_logging(_FakeConfig("json"))

        assert len(self.root.handlers) == 2, "Wrong number of handlers defined"
        stream_handler = self.root.handlers[0]
        self.assert_stream_handler(stream_handler)
        status_handler = self.root.handlers[-1]
        self.assert_status_handler(status_handler)
        assert isinstance(stream_handler.formatter, FiaasFormatter), "Should use logstash formatter"

    def test_debug_logging(self):
        init_logging(_FakeConfig(debug=True))
        assert self.root.level == logging.DEBUG

    def test_json_log_has_extra(self, app_spec):
        set_extras(app_spec)
        init_logging(_FakeConfig("json"))
        stream_handler = self.root.handlers[0]
        log_buffer = StringIO()
        stream_handler.stream = log_buffer
        self.root.info(TEST_MESSAGE)
        log_entry = json.loads(log_buffer.getvalue())
        assert TEST_MESSAGE in log_entry["message"]
        assert log_entry["extras"]["namespace"] == app_spec.namespace
        assert log_entry["extras"]["app_name"] == app_spec.name
        assert log_entry["extras"]["deployment_id"] == app_spec.deployment_id


class _FakeConfig(object):
    def __init__(self, log_format="plain", debug=False):
        self.log_format = log_format
        self.debug = debug
