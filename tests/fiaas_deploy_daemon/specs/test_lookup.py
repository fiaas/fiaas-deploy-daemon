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


import pytest

from fiaas_deploy_daemon.specs.factory import InvalidConfiguration
from fiaas_deploy_daemon.specs.lookup import LookupMapping

CONFIG = {"object": {"complex": {"first": 1, "second": 2}}, "list": ["one", "two", "three"]}

DEFAULTS = {"object": {"simple": 1, "complex": {}}, "list": []}


class TestLookup(object):
    @pytest.fixture
    def lookup(self):
        return LookupMapping(CONFIG, DEFAULTS)

    def test_dict(self, lookup):
        assert lookup["object"]["simple"] == 1
        assert lookup["object"]["complex"] == {"first": 1, "second": 2}
        assert lookup["object"]["complex"]["first"] == 1

    def test_list(self, lookup):
        assert lookup["list"] == ["one", "two", "three"]
        assert lookup["list"][0] == "one"
        assert lookup["list"][-1] == "three"

    @pytest.mark.parametrize(
        "type,expected",
        (
            ("object", 2),
            ("list", 3),
        ),
    )
    def test_len(self, lookup, type, expected):
        assert len(lookup[type]) == expected

    def test_items(self, lookup):
        assert list(lookup["object"].items()) == [("simple", 1), ("complex", {"first": 1, "second": 2})]

    @pytest.mark.parametrize(
        "config,defaults",
        ((CONFIG, 1), (CONFIG, True), (CONFIG, "string"), (1, DEFAULTS), (True, DEFAULTS), ("string", DEFAULTS)),
    )
    def test_incompatible_types(self, config, defaults):
        with pytest.raises(InvalidConfiguration):
            LookupMapping(config, defaults)

    @pytest.mark.parametrize(
        "config,defaults",
        (
            (None, 1),
            (None, True),
            (None, "string"),
            (None, DEFAULTS),
            (1, None),
            (True, None),
            ("string", None),
            (CONFIG, None),
        ),
    )
    def test_ignore_empty(self, config, defaults):
        LookupMapping(config, defaults)
