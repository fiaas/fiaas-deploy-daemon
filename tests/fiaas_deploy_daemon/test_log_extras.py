#!/usr/bin/env python
# -*- coding: utf-8
import logging

from fiaas_deploy_daemon.log_extras import StatusHandler, set_extras, get_final_logs

TEST_MESSAGE = "This is a test log message"


class TestLogExtras(object):
    def test_status_log_has_extra(self, app_spec):
        set_extras(app_spec)
        logger = logging.getLogger("test.log.extras")
        logger.addHandler(StatusHandler())
        logger.warning(TEST_MESSAGE)
        logs = get_final_logs(app_spec)
        assert len(logs) == 1
        log_message = logs[0]
        assert TEST_MESSAGE in log_message
        assert app_spec.name in log_message
        assert app_spec.namespace in log_message
