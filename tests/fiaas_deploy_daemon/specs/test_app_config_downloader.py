
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

# coding: utf-8
import os

import pytest
from requests import HTTPError, Session
from requests_file import FileAdapter
from yaml import YAMLError

from fiaas_deploy_daemon.specs.app_config_downloader import AppConfigDownloader


class TestAppConfigDownloader(object):

    @pytest.fixture
    def session(self):
        session = Session()
        session.mount("file://", FileAdapter())
        return session

    def test_get_app_spec(self, request, session):
        url = 'file://{}'.format(os.path.join(request.fspath.dirpath().strpath, 'data', 'v2minimal.yml'))
        app_config = AppConfigDownloader(session).get(url)
        assert app_config['version'] == 2

    def test_failed_request_raises_exception(self, session):
        with pytest.raises(HTTPError):
            AppConfigDownloader(session).get("file:///non-existing-file")

    def test_invalid_json_raises_yaml_error(self, request, session):
        url = 'file://{}'.format(os.path.join(request.fspath.dirpath().strpath, 'data', 'invalid.yml'))
        with pytest.raises(YAMLError):
            AppConfigDownloader(session).get(url)
