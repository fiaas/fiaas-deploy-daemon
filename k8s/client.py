#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

import requests
from requests import RequestException

from . import config

DEFAULT_TIMEOUT_SECONDS = 10
LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())


class K8sClientException(RequestException):
    pass


class NotFound(K8sClientException):
    """The resource was not found, and the operation could not be completed"""


class ServerError(K8sClientException):
    """The API-server returned an internal error"""


class ClientError(K8sClientException):
    """The client made a bad request"""


class Client(object):
    _session = requests.Session()

    @classmethod
    def clear_session(cls):
        cls._session = requests.Session()

    @classmethod
    def init_session(cls):
        if "Authorization" not in cls._session.headers and config.api_token:
            cls._session.headers.update({"Authorization": "Bearer {}".format(config.api_token)})
        if cls._session.cert is None and config.cert:
            cls._session.cert = config.cert
        cls._session.verify = config.verify_ssl
        if not config.verify_ssl:
            import requests.packages.urllib3 as urllib3
            urllib3.disable_warnings()

    def get(self, url, timeout=DEFAULT_TIMEOUT_SECONDS, **kwargs):
        return self._call("GET", url, timeout=timeout, **kwargs)

    def delete(self, url, timeout=DEFAULT_TIMEOUT_SECONDS):
        return self._call("DELETE", url, timeout=timeout)

    def post(self, url, body, timeout=DEFAULT_TIMEOUT_SECONDS):
        return self._call("POST", url, body, timeout=timeout)

    def put(self, url, body, timeout=DEFAULT_TIMEOUT_SECONDS):
        return self._call("PUT", url, body, timeout=timeout)

    def _call(self, method, url, body=None, timeout=DEFAULT_TIMEOUT_SECONDS, **kwargs):
        self.init_session()
        resp = self._session.request(method, config.api_server + url, json=body, timeout=timeout, **kwargs)
        self._raise_on_status(resp)
        return resp

    @staticmethod
    def _raise_on_status(resp):
        if resp.status_code < 400:
            return
        elif resp.status_code == 404:
            exc = NotFound
        elif 400 <= resp.status_code < 500:
            exc = ClientError
        else:
            exc = ServerError
        http_error_msg = Client._build_error_message(resp)
        raise exc(http_error_msg, response=resp)

    @staticmethod
    def _build_error_message(resp):
        request = resp.request
        message = ['{:d}: {:s} for url: {:s}'.format(resp.status_code, resp.reason, resp.url)]
        Client._add_causes(message, resp)
        Client._add_request(message, request)
        Client._add_response(message, resp)
        return "\n".join(message)

    @staticmethod
    def _add_causes(message, resp):
        try:
            json_response = resp.json()
            json_causes = json_response.get(u"details", {}).get(u"causes", {})
            if json_causes:
                message.append("Causes:")
                message.extend("\t{}: {}".format(d[u"field"], d[u"message"]) for d in json_causes)
        except Exception as e:
            LOG.debug("Exception when dealing with client error response: %s", e)
            LOG.debug("Response: %r", resp.text)

    @staticmethod
    def _add_response(message, resp):
        message.append("Response:")
        Client._add_headers(message, resp.headers, "<<<")
        if resp.text:
            message.append("<<< ")
            message.extend("<<< {}".format(line) for line in resp.text.splitlines())

    @staticmethod
    def _add_request(message, request):
        message.append("Request:")
        message.append(">>> {method} {url}".format(method=request.method, url=request.url))
        Client._add_headers(message, request.headers, ">>>")
        if request.body:
            message.append(">>> ")
            message.extend(">>> {}".format(line) for line in request.body.splitlines())

    @staticmethod
    def _add_headers(message, headers, prefix):
        for key, value in headers.items():
            message.append("{} {}: {}".format(prefix, key, value))
