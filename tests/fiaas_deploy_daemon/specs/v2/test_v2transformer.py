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

from fiaas_deploy_daemon.specs.lookup import LookupMapping
from fiaas_deploy_daemon.specs.v2.transformer import (
    Transformer,
    _get,
    _set,
    RESOURCE_UNDEFINED_UGLYHACK,
    _flatten,
    _remove_intersect,
)


class TestTransformer(object):
    @pytest.fixture
    def data(self):
        return {"first": {"second": {"third": {"one": 1, "string": "some string"}}}}

    @pytest.fixture
    def transformer(self):
        return Transformer()

    @pytest.mark.parametrize(
        "filename",
        (
            "v2minimal",
            "full_config",
            "host",
            "multiple_ports",
            "tcp_config",
            "partial_override",
            "only_liveness",
        ),
    )
    def test_transformation(self, filename, transformer, load_app_config_testdata, load_app_config_transformations):
        config = load_app_config_testdata(filename)
        expected = load_app_config_transformations(filename)
        # See the docstring for RESOURCE_UNDEFINED_UGLYHACK
        for requirement_type in ("limits", "requests"):
            for resource in ("cpu", "memory"):
                if expected["resources"][requirement_type][resource] is None:
                    expected["resources"][requirement_type][resource] = RESOURCE_UNDEFINED_UGLYHACK
        actual = transformer(config)
        assert expected == actual

    def test_get(self, data):
        assert _get(data, ("first", "second", "third", "one")) == 1
        assert _get(data, ("first", "second", "third", "string")) == "some string"

    def test_set(self, data):
        _set(data, ("one",), "one")
        assert data["one"] == "one"
        _set(data, ("first", "two"), "two")
        assert data["first"]["two"] == "two"
        _set(data, ("first", "alternative", "crazy"), "crazy")
        assert data["first"]["alternative"]["crazy"] == "crazy"

    def test_flatten_creates_dicts(self):
        x = {
            "prometheus": LookupMapping(
                config={"path": "/xxx"},
                defaults={"path": "/internal-backstage/prometheus", "enabled": True, "port": "http"},
            )
        }
        assert _flatten(x) == {"prometheus": {"path": "/xxx", "enabled": True, "port": "http"}}

    @pytest.mark.parametrize(
        "filename",
        (
            "v2minimal",
            "full_config",
            "host",
            "multiple_ports",
            "tcp_config",
            "partial_override",
            "only_liveness",
        ),
    )
    def test_transformation_strips_defaults(
        self, filename, transformer, load_app_config_testdata, load_app_config_transformations
    ):
        config = load_app_config_testdata(filename)
        expected = load_app_config_transformations("strip_defaults/" + filename)
        actual = transformer(config, strip_defaults=True)
        assert expected == actual

    @pytest.mark.parametrize(
        "test_input, expected",
        (
            pytest.param(({"first": 1}, {"first": 1}), {}, id="removes identical values"),
            pytest.param(
                ({"first": [{"yy": 123, "zz": 456, "xx": 777}]}, {"first": [{"yy": 123, "zz": 456, "xx": 777}]}),
                {},
                id="removes identical values from single item dict list",
            ),
            pytest.param(
                ({"first": [{"yy": 1}]}, {"first": [{"yy": 1, "zz": 2, "xx": 3}]}),
                {},
                id="removes items from single item dict list that are subset",
            ),
            pytest.param(
                ({"first": [{"yy": 1, "xx": 2, "zz": 3}]}, {"first": [{"yy": 1, "xx": 3}]}),
                {"first": [{"xx": 2, "zz": 3}]},
                id="leaves items from single item dict list that are different",
            ),
            pytest.param(
                ({"first": {"yy": 1}}, {"first": {"yy": 1, "zz": 2, "xx": 3}}),
                {},
                id="removes dict values that are the same",
            ),
        ),
    )
    def test_remove_intersect(self, test_input, expected):
        assert _remove_intersect(test_input[0], test_input[1]) == expected
