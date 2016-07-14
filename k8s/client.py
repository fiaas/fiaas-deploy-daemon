#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import logging
from pprint import pformat

import requests
from requests import RequestException

from . import config


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
    def init_session(cls):
        if "Authorization" not in cls._session.headers:
            cls._session.headers.update({"Authorization": "Bearer {}".format(config.api_token)})
            cls._session.verify = config.verify_ssl

    def get(self, url, **kwargs):
        return self._call("GET", url, **kwargs)

    def delete(self, url):
        return self._call("DELETE", url)

    def post(self, url, body):
        return self._call("POST", url, body)

    def put(self, url, body):
        return self._call("PUT", url, body)

    def _call(self, method, url, body=None, **kwargs):
        self.init_session()
        resp = self._session.request(method, config.api_server + url, json=body, timeout=10, **kwargs)
        self._raise_on_status(resp)
        return resp

    @staticmethod
    def _raise_on_status(resp):
        if resp.status_code == 404:
            raise NotFound(response=resp)
        elif 400 <= resp.status_code < 500:
            json_response = resp.json()
            LOG.debug("Client error request: %s", Client._format_request(resp.request))
            LOG.debug("Client error response: %s", pformat(json_response))
            causes = json_response.get(u"details", {}).get(u"causes", {})
            lines = ["{}: {}".format(d[u"field"], d[u"message"]) for d in causes]
            http_error_msg = '{0:d} Client Error: {1:s} for url: {2:s}\nCauses: \n\t{3:s}'.format(
                    resp.status_code, resp.reason, resp.url, "\n\t".join(lines))
            raise ClientError(http_error_msg, response=resp)

        elif 500 <= resp.status_code < 600:
            http_error_msg = '%s Server Error: %s for url: %s' % (resp.status_code, resp.reason, resp.url)
            raise ServerError(http_error_msg, response=resp)

    @staticmethod
    def _format_request(request):
        return "Request({})".format(pformat({
            "method": request.method,
            "url": request.url,
            "headers": request.headers,
            "body": request.body
        }))
