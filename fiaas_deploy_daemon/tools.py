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


import logging
from Queue import Queue
from collections import Iterator

from k8s import config
from requests_toolbelt.utils.dump import dump_all


def merge_dicts(*args):
    result = {}
    for d in args:
        result.update(d)
    return result


def log_request_response(resp, *args, **kwargs):
    if resp.url.startswith(config.api_server):
        return  # k8s library already does its own dumping, we don't need to do it here
    log = logging.getLogger(__name__)
    data = dump_all(resp, "<<<", ">>>")
    log.debug("Request/Response\n" + data)


class IterableQueue(Queue, Iterator):
    def next(self):
        return self.get()
