#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import unicode_literals, absolute_import

from datetime import datetime

import mock
import pytest
import requests

from fiaas_deploy_daemon.usage_reporting.dev_hose_auth import DevHoseAuth


class TestDevHoseAuth(object):
    @pytest.fixture
    def mock_request(self):
        r = mock.create_autospec(requests.PreparedRequest(), spec_set=True, instance=True)
        r.body = "payload"
        r.path_url = "uri"
        r.headers = {}
        return r

    def test_simple_string_to_sign(self, mock_request):
        auth = DevHoseAuth(b"dummy key", "tenant")
        string_to_sign = auth._create_string_to_sign(mock_request, 100, "nonce")
        assert string_to_sign == "uri\nnonce\n100000\neyJ0eXBlIjogInRlbmFudCJ9\npayload\n"

    def test_key_can_have_extra_newline(self, mock_request):
        auth = DevHoseAuth(b"dummy key\n", "tenant")
        string_to_sign = auth._create_string_to_sign(mock_request, 100, "nonce")
        assert string_to_sign == "uri\nnonce\n100000\neyJ0eXBlIjogInRlbmFudCJ9\npayload\n"

    def test_escaped_string_to_sign(self, mock_request):
        mock_request.body = "߷\u23FB@/"
        mock_request.path_url = "/߷\u23FB@/a-zA-Z0-9.-~_@:!$&'()*+,;=/?"
        auth = DevHoseAuth(b"dummy key", "߷\u23FB@/")
        timestamp = (datetime(2017, 9, 26, 11, 16, 25, 439000) - datetime(1970, 1, 1)).total_seconds()
        string_to_sign = auth._create_string_to_sign(mock_request, timestamp, "߷\u23FB@/")
        assert string_to_sign == "/%DF%B7%E2%8F%BB@/a-zA-Z0-9.-~_@:!$&'()*+,;=/?\n" \
                                 "%DF%B7%E2%8F%BB%40%2F\n" \
                                 "1506424585000\n" \
                                 "eyJ0eXBlIjogIlx1MDdmN1x1MjNmYkAvIn0%3D\n" \
                                 "%DF%B7%E2%8F%BB%40%2F\n"

    def test_signing(self, mock_request):
        with mock.patch("fiaas_deploy_daemon.usage_reporting.dev_hose_auth.uuid.uuid4") as m_uuid, \
                mock.patch("fiaas_deploy_daemon.usage_reporting.dev_hose_auth.time.time") as m_time:
            m_uuid.return_value = "mocked_nonce"
            m_time.return_value = 1514764861.000001
            auth = DevHoseAuth(b"dummy key", "tenant")
            auth(mock_request)
            assert mock_request.headers["DevHose-AuthContext"] == "eyJ0eXBlIjogInRlbmFudCJ9"
            assert mock_request.headers["DevHose-Nonce"] == "mocked_nonce"
            assert mock_request.headers["Date"] == "Mon, 01 Jan 2018 00:01:01 -0000"
