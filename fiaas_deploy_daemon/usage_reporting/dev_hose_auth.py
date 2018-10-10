#!/usr/bin/env python
# -*- coding: utf-8
import base64
import email.utils
import hashlib
import hmac
import json
import time
import uuid
from urllib import quote, quote_plus

from requests.auth import AuthBase


class DevHoseAuth(AuthBase):
    def __init__(self, key, tenant):
        self._key = base64.b64decode(key)
        self._auth_context = base64.b64encode(json.dumps({"type": tenant}))

    def __call__(self, r):
        timestamp = time.time()
        nonce = str(uuid.uuid4())
        r.headers["Content-Signature"] = self._calculate_signature(r, timestamp, nonce)
        r.headers["DevHose-AuthContext"] = self._auth_context
        r.headers["DevHose-Nonce"] = nonce
        r.headers["Date"] = email.utils.formatdate(timestamp)
        return r

    def _calculate_signature(self, r, timestamp, nonce):
        signature = hmac.new(self._key, digestmod=hashlib.sha256)
        string_to_sign = self._create_string_to_sign(r, timestamp, nonce)
        signature.update(string_to_sign)
        return base64.b64encode(signature.digest())

    def _create_string_to_sign(self, r, timestamp, nonce):
        return "\n".join((
            quote(r.path_url.encode("utf-8"), b".-~_@:!$&'()*+,;=/?"),
            quote_plus(nonce.encode("utf-8")),
            str(int(timestamp) * 1000),
            quote_plus(self._auth_context),
            quote_plus(r.body.encode("utf-8")),
            ""
        ))
