#!/usr/bin/env python
# -*- coding: utf-8

# Copyright 2017-2021 The FIAAS Authors
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
import json
import logging
import posixpath
import urlparse

LOG = logging.getLogger(__name__)


class ExtensionHookCaller(object):

    def __init__(self, config, session):
        self._url = config.hook_service
        self._session = session

    def apply(self, obj, app_spec):
        if self._url is None:
            return obj
        url = urlparse.urljoin(self._url, "fiaas/deploy/")
        url = posixpath.join(url, type(obj).__name__)
        dump = json.dumps({"object": obj.as_dict(), "application": app_spec.app})
        response = self._session.post(
            url,
            data=dump,
            headers={'Content-Type': 'application/json', 'Accept': 'application/json'}
        )
        if response.status_code == 200:
            data = response.json()
            obj.update_from_dict(data)
        elif response.status_code != 404:
            response.raise_for_status()
