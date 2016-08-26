#!/usr/bin/env python
# -*- coding: utf-8

import collections


class _Lookup(object):
    def __init__(self, config, defaults):
        self._config = config
        self._defaults = defaults

    def __getitem__(self, key):
        c_value = self.get_c_value(key)
        d_value = self.get_d_value(key)
        if isinstance(d_value, (list, tuple)):
            return _LookupList(c_value, d_value)
        if isinstance(d_value, collections.Mapping):
            return LookupMapping(c_value, d_value)
        if c_value is None:
            return d_value
        return c_value

    def get_d_value(self, key):
        return self._get_value(self._defaults, key)

    def get_c_value(self, key):
        return self._get_value(self._config, key) if self._config else None

    def _get_value(self, col, key):
        raise NotImplementedError("This should not happen")

    def raw(self):
        return self._config if self._config else self._defaults


class LookupMapping(_Lookup):
    def _get_value(self, col, key):
        d_value = col.get(key)
        return d_value


class _LookupList(_Lookup):
    def __getitem__(self, idx):
        if self._config:
            if idx >= len(self._config):
                raise StopIteration()
        elif idx >= len(self._defaults):
            raise StopIteration()
        return super(_LookupList, self).__getitem__(idx)

    def get_d_value(self, idx):
        return super(_LookupList, self).get_d_value(0)

    def _get_value(self, col, idx):
        if idx >= len(col):
            return None
        return col[idx]
