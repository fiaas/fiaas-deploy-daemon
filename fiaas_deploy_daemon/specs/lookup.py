#!/usr/bin/env python
# -*- coding: utf-8

import collections
from itertools import izip_longest


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

    def __len__(self):
        return max(_len(self._defaults), _len(self._config))

    def __repr__(self):
        return "%s(config=%r, defaults=%r)" % (self.__class__.__name__, self._config, self._defaults)


class LookupMapping(_Lookup, collections.Mapping):
    def _get_value(self, col, key):
        d_value = col.get(key)
        return d_value

    def __iter__(self):
        return iter(self._defaults) if _len(self._defaults) > _len(self._config) else iter(self._config)


class _LookupList(_Lookup, collections.Sequence):
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

    def __eq__(self, other):
        if not isinstance(other, collections.Sequence):
            return NotImplemented
        for self_i, other_i in izip_longest(self, other, fillvalue=object()):
            if self_i != other_i:
                return False
        return True


def _len(d):
    return len(d) if d is not None else -1
