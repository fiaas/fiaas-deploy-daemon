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

from __future__ import unicode_literals, absolute_import

import base64
from datetime import datetime

import mock
import pytest
import requests

from fiaas_deploy_daemon.usage_reporting.dev_hose_auth import DevHoseAuth


class TestDevHoseAuth(object):
    _KEY = base64.b64encode(b"dummy key")

    @pytest.fixture
    def mock_request(self):
        r = mock.create_autospec(requests.PreparedRequest(), spec_set=True, instance=True)
        r.body = "payload"
        r.path_url = "uri"
        r.headers = {}
        return r

    def test_simple_string_to_sign(self, mock_request):
        auth = DevHoseAuth(self._KEY, "tenant")
        string_to_sign = auth._create_string_to_sign(mock_request, 100, "nonce")
        assert string_to_sign == "uri\nnonce\n100000\neyJ0eXBlIjogInRlbmFudCJ9\npayload\n"

    def test_escaped_string_to_sign(self, mock_request):
        mock_request.body = "߷\u23FB@/"
        mock_request.path_url = "/߷\u23FB@/a-zA-Z0-9.-~_@:!$&'()*+,;=/?"
        auth = DevHoseAuth(self._KEY, "߷\u23FB@/")
        timestamp = (datetime(2017, 9, 26, 11, 16, 25, 439000) - datetime(1970, 1, 1)).total_seconds()
        string_to_sign = auth._create_string_to_sign(mock_request, timestamp, "߷\u23FB@/")
        assert string_to_sign == "/%DF%B7%E2%8F%BB@/a-zA-Z0-9.-~_@:!$&'()*+,;=/?\n" \
                                 "%DF%B7%E2%8F%BB%40%2F\n" \
                                 "1506424585000\n" \
                                 "eyJ0eXBlIjogIlx1MDdmN1x1MjNmYkAvIn0%3D\n" \
                                 "%DF%B7%E2%8F%BB%40%2F\n"

    @pytest.mark.parametrize("key", (_KEY, b"\n" + _KEY, _KEY + b"\n"))
    def test_signing(self, mock_request, key):
        with mock.patch("fiaas_deploy_daemon.usage_reporting.dev_hose_auth.uuid.uuid4") as m_uuid, \
                mock.patch("fiaas_deploy_daemon.usage_reporting.dev_hose_auth.time.time") as m_time:
            m_uuid.return_value = "mocked_nonce"
            m_time.return_value = 1514764861.000001
            auth = DevHoseAuth(key, "tenant")
            auth(mock_request)
            assert mock_request.headers["DevHose-AuthContext"] == "eyJ0eXBlIjogInRlbmFudCJ9"
            assert mock_request.headers["DevHose-Nonce"] == "mocked_nonce"
            assert mock_request.headers["Date"] == "Mon, 01 Jan 2018 00:01:01 -0000"
            assert mock_request.headers["Content-Signature"] == "tYyKot+bWabhxpsvWJunmFFqZ6f/LfY361xpkB3svDQ="
