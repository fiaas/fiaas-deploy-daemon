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
import base64
import email.utils
import hashlib
import hmac
import json
import time
import uuid
from urllib.parse import quote, quote_plus

from requests.auth import AuthBase


class DevHoseAuth(AuthBase):
    def __init__(self, key, tenant):
        self._key = base64.b64decode(key.strip())
        self._auth_context = base64.b64encode(json.dumps({"type": tenant}).encode("utf-8")).decode("utf-8")

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
        signature.update(string_to_sign.encode("utf-8"))
        return base64.b64encode(signature.digest()).decode("utf-8")

    def _create_string_to_sign(self, r, timestamp, nonce):
        return "\n".join((
            quote(r.path_url.encode("utf-8"), b".-~_@:!$&'()*+,;=/?"),
            quote_plus(nonce.encode("utf-8")),
            str(int(timestamp) * 1000),
            quote_plus(self._auth_context),
            quote_plus(r.body.encode("utf-8")),
            ""
        ))
