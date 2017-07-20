#!/usr/bin/env python
# -*- coding: utf-8

import logging
import sys

from fiaas_deploy_daemon.logsetup import init_logging, FiaasFormatter


class TestLogSetup(object):
    # This removes the pytest injected handler if it exists
    # without this code, the test would fail under some versions of pytest
    # as yet uncharacterized. Nasty hack for nasty behavior
    def __init__(self):
        logger = logging.getLogger()
        if len(logger.handlers) == 1:
            logger.removeHandler(logger.handlers[0])

    def setup(self):
        self.root = logging.getLogger()

    def teardown(self):
        handlers = list(self.root.handlers)
        for handler in handlers:
            self.root.removeHandler(handler)

    def assert_correct_handler(self, handler):
        assert isinstance(handler, logging.StreamHandler), "Handler is not a StreamHandler"
        assert handler.stream == sys.stdout, "Not streaming to stdout"

    def test_default_behaviour(self):
        init_logging(_FakeConfig())

        assert len(self.root.handlers) == 1, "Wrong number of handlers defined"
        handler = self.root.handlers[0]
        self.assert_correct_handler(handler)
        assert isinstance(handler.formatter, logging.Formatter), "Should use standard formatter"
        assert self.root.level == logging.INFO

    def test_output_json(self):
        init_logging(_FakeConfig("json"))

        assert len(self.root.handlers) == 1, "Wrong number of handlers defined"
        handler = self.root.handlers[0]
        self.assert_correct_handler(handler)
        assert isinstance(handler.formatter, FiaasFormatter), "Should use logstash formatter"

    def test_debug_logging(self):
        init_logging(_FakeConfig(debug=True))
        assert self.root.level == logging.DEBUG


class _FakeConfig(object):
    def __init__(self, log_format="plain", debug=False):
        self.log_format = log_format
        self.debug = debug
