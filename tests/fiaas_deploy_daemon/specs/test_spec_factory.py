#!/usr/bin/env python
# -*- coding: utf-8

import pytest
from mock import ANY, create_autospec

from fiaas_deploy_daemon.specs.factory import SpecFactory, InvalidConfiguration, BaseFactory, BaseTransformer

IMAGE = u"finntech/docker-image:some-version"
NAME = u"application-name"
TEAMS = "IO"
TAGS = "Foo"
DEPLOYMENT_ID = "deployment_id"


class TestSpecFactory(object):
    @pytest.fixture
    def v1(self):
        return create_autospec(BaseTransformer, spec_set=True, version=1, return_value={"version": 2})

    @pytest.fixture
    def v2(self):
        return create_autospec(BaseTransformer, spec_set=True, version=2, return_value={"version": 3})

    @pytest.fixture
    def v3(self):
        return create_autospec(BaseFactory, spec_set=True, version=3)

    @pytest.fixture
    def transformers(self, v1, v2):
        return {1: v1, 2: v2}

    @pytest.fixture()
    def factory(self, v3, transformers):
        return SpecFactory(v3, transformers)

    @pytest.mark.parametrize("version,mock_to_call", [
        (None, "v1"),
        (1, "v1"),
        (2, "v2")
    ])
    def test_dispatch_to_correct_transformer(self, request, factory, version, mock_to_call):
        minimal_config = {}
        if version:
            minimal_config["version"] = version
        factory(NAME, IMAGE, minimal_config, TEAMS, TAGS, DEPLOYMENT_ID)
        mock_factory = request.getfuncargvalue(mock_to_call)
        mock_factory.assert_called_with(minimal_config)

    @pytest.mark.parametrize("version", [1, 2, 3])
    def test_parsed_by_current_version(self, factory, version, v3):
        factory(NAME, IMAGE, {"version": version}, TEAMS, TAGS, DEPLOYMENT_ID)
        v3.assert_called_with(NAME, IMAGE, TEAMS, TAGS, ANY, DEPLOYMENT_ID)

    def test_raise_invalid_config_if_version_not_supported(self, factory):
        with pytest.raises(InvalidConfiguration):
            factory(NAME, IMAGE, {"version": 999}, TEAMS, TAGS, DEPLOYMENT_ID)
