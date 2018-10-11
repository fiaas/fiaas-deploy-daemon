#!/usr/bin/env python
# -*- coding: utf-8

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
