#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import unicode_literals, absolute_import

import base64
import collections
import email
import hashlib
import hmac
import json
import random
import string
import time
from urllib import quote, quote_plus

from blinker import signal
from requests.auth import AuthBase

from fiaas_deploy_daemon.base_thread import DaemonThread
from fiaas_deploy_daemon.deployer.bookkeeper import DEPLOY_FAILED, DEPLOY_STARTED, DEPLOY_SUCCESS
from fiaas_deploy_daemon.tools import IterableQueue

UsageEvent = collections.namedtuple("UsageEvent", ("status", "app_spec"))


class UsageReporter(DaemonThread):
    def __init__(self, config, usage_transformer, session):
        super(UsageReporter, self).__init__()
        self._session = session
        self._transformer = usage_transformer
        self._event_queue = IterableQueue()
        self._usage_endpoint = config.usage_endpoint
        signal(DEPLOY_STARTED).connect(self._handle_started)
        signal(DEPLOY_SUCCESS).connect(self._handle_success)
        signal(DEPLOY_FAILED).connect(self._handle_failed)

    def _handle_signal(self, status, app_spec):
        self._event_queue.put(UsageEvent(status, app_spec))

    def _handle_started(self, sender, app_spec):
        self._handle_signal(u"STARTED", app_spec)

    def _handle_failed(self, sender, app_spec):
        self._handle_signal(u"FAILED", app_spec)

    def _handle_success(self, sender, app_spec):
        self._handle_signal(u"SUCCESS", app_spec)

    def __call__(self):
        for event in self._event_queue:
            self._handle_event(event)

    def _handle_event(self, event):
        data = self._transformer.transform(event.status, event.app_spec)
        self._session.post(self._usage_endpoint, data=data)


class DevHoseAuth(AuthBase):
    AUTH_CONTEXT = base64.b64encode(json.dumps({"type": "delivery"}))
    NONCE_CHARACTERS = string.ascii_letters + string.digits

    def __init__(self, key):
        self._key = key

    def __call__(self, r):
        timestamp = int(time.time())
        nonce = self._generate_nonce()
        r.headers["Content-Signature"] = self._calculate_signature(r, timestamp, nonce)
        r.headers["DevHose-AuthContext"] = self.AUTH_CONTEXT
        r.headers["DevHose-Nonce"] = nonce
        r.headers["Date"] = email.utils.formatdate(timestamp)
        return r

    def _calculate_signature(self, r, timestamp, nonce):
        signature = hmac.new(self._key, digestmod=hashlib.sha256)
        signature.update(quote(r.path_url.encode("utf-8"), ".-~_@:!$&'()*+,;=/?"))
        signature.update(quote_plus(nonce.encode("utf-8")))
        signature.update(str(timestamp*1000).encode("utf-8"))
        signature.update(quote_plus(self.AUTH_CONTEXT.encode("utf-8")))
        signature.update(quote_plus(r.body.encode("utf-8")))
        return base64.b64encode(signature.digest())

    def _generate_nonce(self):
        return "".join(random.choice(self.NONCE_CHARACTERS) for _ in range(64))


if __name__ == "__main__":
    import requests
    body = {"test": "data"}
    auth = DevHoseAuth("my key".encode("utf-8"))
    resp = requests.post("https://devhose.ep.schibsted.io/devhose/null", data=body, auth=auth)
    print(resp.json())
    resp.raise_for_status()
