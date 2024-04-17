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
import collections.abc
from itertools import zip_longest

from .factory import InvalidConfiguration


class _Lookup(object):
    def __init__(self, config, defaults):
        if config and defaults and not isinstance(config, type(defaults)):
            raise InvalidConfiguration("{!r} is not of the expected type {!r}".format(config, type(defaults)))
        self._config = config
        self._defaults = defaults

    def __getitem__(self, key):
        config_value = self.get_config_value(key)
        default_value = self.get_default_value(key)
        if isinstance(default_value, (list, tuple)):
            return _LookupList(config_value, default_value)
        if isinstance(default_value, collections.abc.Mapping):
            return LookupMapping(config_value, default_value)
        if config_value is None:
            return default_value
        return config_value

    def get_default_value(self, key):
        return self._get_value(self._defaults, key)

    def get_config_value(self, key):
        return self._get_value(self._config, key) if self._config else None

    def _get_value(self, col, key):
        raise NotImplementedError("This should not happen")

    def raw(self):
        return self._config if self._config else self._defaults

    def __repr__(self):
        return "%s(config=%r, defaults=%r)" % (self.__class__.__name__, self._config, self._defaults)


class LookupMapping(_Lookup, collections.abc.Mapping):
    def _get_value(self, col, key):
        default_value = col.get(key)
        return default_value

    def __len__(self):
        return max(_len(self._defaults), _len(self._config))

    def __iter__(self):
        return iter(self._defaults) if _len(self._defaults) > _len(self._config) else iter(self._config)


class _LookupList(_Lookup, collections.abc.Sequence):
    def __getitem__(self, idx):
        if self._config is not None:
            if idx >= len(self._config):
                raise IndexError("Index {} out of bounds for sequence of length {}".format(idx, len(self._config)))
        elif idx >= len(self._defaults):
            raise IndexError("Index {} out of bounds for sequence of length {}".format(idx, len(self._defaults)))
        return super(_LookupList, self).__getitem__(idx)

    def __len__(self):
        if self._config is not None:
            return len(self._config)
        return len(self._defaults)

    def get_default_value(self, idx):
        return super(_LookupList, self).get_default_value(0)

    def _get_value(self, col, idx):
        if idx >= len(col):
            return None
        return col[idx]

    def __eq__(self, other):
        if not isinstance(other, collections.abc.Sequence):
            return NotImplemented
        for self_i, other_i in zip_longest(self, other, fillvalue=object()):
            if self_i != other_i:
                return False
        return True


def _len(d):
    return len(d) if d is not None else -1
