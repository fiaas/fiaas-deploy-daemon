#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import unicode_literals, absolute_import

import pytest

from fiaas_deploy_daemon.specs.lookup import LookupMapping


CONFIG = {
    "object": {
        "complex": {
            "first": 1,
            "second": 2
        }
    },
    "list": [
        "one",
        "two",
        "three"
    ]
}

DEFAULTS = {
    "object": {
        "simple": 1,
        "complex": {}
    },
    "list": []
}


class TestLookup(object):
    @pytest.fixture
    def lookup(self):
        return LookupMapping(CONFIG, DEFAULTS)

    def test_dict(self, lookup):
        assert lookup["object"]["simple"] == 1
        assert lookup["object"]["complex"] == {
            "first": 1, "second": 2
        }
        assert lookup["object"]["complex"]["first"] == 1

    def test_list(self, lookup):
        assert lookup["list"] == ["one", "two", "three"]
        assert lookup["list"][0] == "one"
        assert lookup["list"][-1] == "three"

    @pytest.mark.parametrize("type,expected", (
            ("object", 2),
            ("list", 3),
    ))
    def test_len(self, lookup, type, expected):
        assert len(lookup[type]) == expected

    def test_items(self, lookup):
        assert lookup["object"].items() == [("simple", 1), ("complex", {"first": 1, "second": 2})]
