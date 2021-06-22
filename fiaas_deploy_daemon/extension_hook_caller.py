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
from collections import OrderedDict

from six import string_types


LOG = logging.getLogger(__name__)


class ExtensionHookCaller(object):

    def __init__(self, config, session):
        self._url = config.hook_service
        self._session = session

    def apply(self, kind, obj, app_spec):
        if self._url is None:
            return obj
        url = str(self._url) + "/fiaas/deploy/" + str(kind)
        dump = json.dumps({"object": obj.as_dict(), "application": self._app_spec_to_dict(app_spec)})
        response = self._session.post(
            url,
            data=dump,
            headers={'Content-Type': 'application/json', 'Accept': 'application/json'}
        )
        if response.status_code == 200:
            data = response.json()
            obj.update_from_dict(data)
        elif response.status_code != 404:
            raise Exception("The api call to " + url + " returns an status code of " + response.status_code)

    @staticmethod
    def _app_spec_to_dict(app_spec):
        def _obj_to_dict(obj):
            ''' check for namedtuples and collections that could contain namedtuples, recursively,
            to turn them into dicts
            '''
            if hasattr(obj, "_asdict"):  # detect namedtuple
                return OrderedDict(zip(obj._fields, (_obj_to_dict(item) for item in obj)))
            elif isinstance(obj, string_types):  # strings are iterable but they can't contain namedtuples
                return obj
            elif hasattr(obj, "keys"):
                return OrderedDict(zip(obj.keys(), (_obj_to_dict(item) for item in obj.values())))
            elif hasattr(obj, "__iter__"):
                return [_obj_to_dict(item) for item in obj]
            else:  # non-iterable cannot contain namedtuples
                return obj

        app_spec_dict = _obj_to_dict(app_spec)
        LOG.error(app_spec_dict)
        return app_spec_dict
