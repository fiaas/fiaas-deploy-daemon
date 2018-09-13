#!/usr/bin/env python
# -*- coding: utf-8
from Queue import Queue
from collections import Iterator


def merge_dicts(*args):
    result = {}
    for d in args:
        result.update(d)
    return result


class IterableQueue(Queue, Iterator):
    def next(self):
        return self.get()
