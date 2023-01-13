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
import json
import logging
import sys
from io import StringIO

from unittest import mock
import pytest
from callee import InstanceOf, Attrs, List

from fiaas_deploy_daemon.log_extras import StatusHandler, ExtraFilter, set_extras
from fiaas_deploy_daemon.logsetup import init_logging, FiaasFormatter, _create_default_handler

TEST_MESSAGE = "This is a test log message"


class TestLogSetup(object):
    @pytest.fixture
    def root_logger(self):
        with mock.patch("fiaas_deploy_daemon.logsetup.logging.getLogger") as m:
            root = mock.create_autospec(logging.root, name="mock_root_logger", instance=True, spec_set=True)
            root.level = logging.NOTSET

            def _get(name=None):
                if name is None:
                    return root
                return logging.Logger(name)

            m.side_effect = _get
            yield root

    @staticmethod
    def _describe_stream_handler(formatter):
        return InstanceOf(logging.StreamHandler) & Attrs(
            stream=sys.stdout, filters=List(of=InstanceOf(ExtraFilter)), formatter=InstanceOf(formatter, exact=True)
        )

    @staticmethod
    def _describe_status_handler():
        return InstanceOf(StatusHandler) & Attrs(filters=List(of=InstanceOf(ExtraFilter)))

    def test_default_behaviour(self, root_logger):
        init_logging(_FakeConfig())

        root_logger.addHandler.assert_has_calls(
            (mock.call(self._describe_stream_handler(logging.Formatter)), mock.call(self._describe_status_handler())),
            any_order=True,
        )
        root_logger.setLevel.assert_called_with(logging.INFO)

    def test_output_json(self, root_logger):
        init_logging(_FakeConfig("json"))
        root_logger.addHandler.assert_has_calls(
            (mock.call(self._describe_stream_handler(FiaasFormatter)), mock.call(self._describe_status_handler())),
            any_order=True,
        )

    def test_debug_logging(self, root_logger):
        init_logging(_FakeConfig(debug=True))
        root_logger.setLevel.assert_called_with(logging.DEBUG)

    def test_json_log_has_extra(self, app_spec):
        log = logging.getLogger("test-logger")
        log.setLevel(logging.INFO)
        handler = _create_default_handler(_FakeConfig("json"))
        log_buffer = StringIO()
        handler.stream = log_buffer
        log.addHandler(handler)
        set_extras(app_spec)
        log.info(TEST_MESSAGE)
        log_entry = json.loads(log_buffer.getvalue())
        assert TEST_MESSAGE in log_entry["message"]
        assert log_entry["extras"]["namespace"] == app_spec.namespace
        assert log_entry["extras"]["app_name"] == app_spec.name
        assert log_entry["extras"]["deployment_id"] == app_spec.deployment_id


class _FakeConfig(object):
    def __init__(self, log_format="plain", debug=False):
        self.log_format = log_format
        self.debug = debug
