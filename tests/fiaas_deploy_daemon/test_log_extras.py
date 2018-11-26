#!/usr/bin/env python
# -*- coding: utf-8
import logging

import pytest

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

    @pytest.fixture
    def spec(self, request, app_spec):
        if request.param:
            kw = {request.param: None}
            return app_spec._replace(**kw)

    @pytest.mark.parametrize("spec,name,namespace,deployment_id", (
            (False, None, "namespace", "deployment_id"),
            (False, "name", None, "deployment_id"),
            (False, "name", "namespace", None),
            (False, None, None, None),
            ("name", None, None, None),
            ("namespace", None, None, None),
            ("deployment_id", None, None, None),
    ), indirect=["spec"])
    def test_require_all_three_fields(self, spec, name, namespace, deployment_id):
        with pytest.raises(TypeError):
            set_extras(app_spec=spec, app_name=name, namespace=namespace, deployment_id=deployment_id)
