#!/usr/bin/env python
# -*- coding: utf-8


def merge_dicts(*args):
    result = {}
    for d in args:
        result.update(d)
    return result
