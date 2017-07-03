#!/usr/bin/env python
# -*- coding: utf-8 -*-

import mock
import pytest

from k8s.client import Client, DEFAULT_TIMEOUT_SECONDS
from k8s import config
from k8s.base import Model, Field


@pytest.mark.usefixtures("k8s_config")
class TestClient(object):
    @pytest.fixture
    def success_response(self):
        resp = mock.MagicMock()
        resp.status_code = 200
        return resp

    @pytest.fixture
    def session(self, success_response):
        with mock.patch("k8s.client.Client._session") as mockk:
            mockk.request.return_value = success_response
            yield mockk

    @pytest.fixture
    def client(self):
        return Client()

    @pytest.fixture
    def url(self):
        return "/api/v1/nodes"

    @pytest.fixture
    def explicit_timeout(self):
        return 60

    def test_get_should_use_default_timeout(self, session, client, url):
        client.get(url)
        session.request.assert_called_once_with("GET", _absolute_url(url), json=None, timeout=DEFAULT_TIMEOUT_SECONDS)

    def test_get_should_propagate_timeout(self, session, client, url, explicit_timeout):
        client.get(url, timeout=explicit_timeout)
        session.request.assert_called_once_with("GET", _absolute_url(url), json=None, timeout=explicit_timeout)

    def test_delete_should_use_default_timeout(self, session, client, url):
        client.delete(url)
        session.request.assert_called_once_with(
            "DELETE", _absolute_url(url), json=None, timeout=DEFAULT_TIMEOUT_SECONDS
        )

    def test_delete_should_propagate_timeout(self, session, client, url, explicit_timeout):
        client.delete(url, timeout=explicit_timeout)
        session.request.assert_called_once_with("DELETE", _absolute_url(url), json=None, timeout=explicit_timeout)

    def test_delete_should_use_default_body(self, session, client, url):
        client.delete(url)
        session.request.assert_called_once_with(
            "DELETE", _absolute_url(url), json=None, timeout=DEFAULT_TIMEOUT_SECONDS
        )

    def test_delete_should_propagate_body(self, session, client, url):
        body = {"kind": "DeleteOptions", "apiVersion": "v1", "propagationPolicy": "Foreground"}
        client.delete(url, body=body)
        session.request.assert_called_once_with(
            "DELETE", _absolute_url(url), json=body, timeout=DEFAULT_TIMEOUT_SECONDS
        )

    def test_post_should_use_default_timeout(self, session, client, url):
        body = {"foo": "bar"}
        client.post(url, body=body)
        session.request.assert_called_once_with("POST", _absolute_url(url), json=body, timeout=DEFAULT_TIMEOUT_SECONDS)

    def test_post_should_propagate_timeout(self, session, client, url, explicit_timeout):
        body = {"foo": "bar"}
        client.post(url, body=body, timeout=explicit_timeout)
        session.request.assert_called_once_with("POST", _absolute_url(url), json=body, timeout=explicit_timeout)

    def test_put_should_use_default_timeout(self, session, client, url):
        body = {"foo": "bar"}
        client.put(url, body=body)
        session.request.assert_called_once_with("PUT", _absolute_url(url), json=body, timeout=DEFAULT_TIMEOUT_SECONDS)

    def test_put_should_propagate_timeout(self, session, client, url, explicit_timeout):
        body = {"foo": "bar"}
        client.put(url, body=body, timeout=explicit_timeout)
        session.request.assert_called_once_with("PUT", _absolute_url(url), json=body, timeout=explicit_timeout)

    def test_watch_list_should_raise_exception_when_watch_list_url_is_not_set_on_metaclass(self, session):
        with pytest.raises(NotImplementedError):
            list(WatchListExampleUnsupported.watch_list())

    def test_watch_list(self, session):
        list(WatchListExample.watch_list())
        session.request.assert_called_once_with(
            "GET", _absolute_url("/watch/example"), json=None, timeout=None, stream=True
        )


def _absolute_url(url):
    return config.api_server + url


class WatchListExample(Model):
    class Meta:
        url_template = '/example'
        watch_list_url = '/watch/example'

    value = Field(int)


class WatchListExampleUnsupported(Model):
    class Meta:
        url_template = '/example'

    value = Field(int)
