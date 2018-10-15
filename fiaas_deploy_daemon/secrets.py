#!/usr/bin/env python
# -*- coding: utf-8

from __future__ import absolute_import, unicode_literals

import os
from collections import namedtuple

Secrets = namedtuple("Secrets", ("usage_reporting_key",))


def resolve_secrets(secrets_directory):
    kwargs = {}
    for field in Secrets._fields:
        fpath = os.path.join(secrets_directory, field)
        if os.path.isfile(fpath):
            with open(fpath) as fobj:
                kwargs[field] = fobj.read().strip()
        else:
            kwargs[field] = None
    return Secrets(**kwargs)
