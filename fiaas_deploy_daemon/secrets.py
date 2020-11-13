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


import os
from collections import namedtuple

Secrets = namedtuple("Secrets", ("usage_reporting_key",))


def resolve_secrets(secrets_directory):
    kwargs = {}
    for field in Secrets._fields:
        filename = field.replace("_", "-")
        fpath = os.path.join(secrets_directory, filename)
        if os.path.isfile(fpath):
            with open(fpath, 'rb') as fobj:
                kwargs[field] = fobj.read().strip()
        else:
            kwargs[field] = None
    return Secrets(**kwargs)
