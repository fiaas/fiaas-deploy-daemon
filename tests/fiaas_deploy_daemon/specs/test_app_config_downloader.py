# coding: utf-8
import os

import pytest
from requests import HTTPError, Session
from requests_file import FileAdapter

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
