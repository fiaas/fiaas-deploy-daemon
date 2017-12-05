#!/usr/bin/env python
# -*- coding: utf-8
import pytest

from fiaas_deploy_daemon.specs.v2.transformer import Transformer, _get, _set, RESOURCE_UNDEFINED_UGLYHACK


class TestTransformer(object):
    @pytest.fixture
    def data(self):
        return {
            "first": {
                "second": {
                    "third": {
                        "one": 1,
                        "string": "some string"
                    }
                }
            }
        }

    @pytest.fixture
    def transformer(self):
        return Transformer()

    @pytest.mark.parametrize("filename", (
        "v2minimal",
        "full_config",
        "host",
        "multiple_ports",
        "tcp_config",
        "partial_override",
    ))
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
