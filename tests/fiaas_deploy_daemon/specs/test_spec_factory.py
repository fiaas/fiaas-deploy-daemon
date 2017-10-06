#!/usr/bin/env python
# -*- coding: utf-8

import pytest
from mock import MagicMock, ANY

from fiaas_deploy_daemon.specs.factory import SpecFactory

IMAGE = u"finntech/docker-image:some-version"
NAME = u"application-name"
TEAMS = "IO"
TAGS = "Foo"
DEPLOYMENT_ID = "deployment_id"


class TestSpecFactory(object):
    @pytest.fixture
    def v1(self):
        return MagicMock()

    @pytest.fixture
    def v2(self):
        return MagicMock()

    @pytest.fixture()
    def factory(self, v1, v2):
        return SpecFactory({1: v1, 2: v2})

    @pytest.mark.parametrize("version,mock_to_call", [
        (None, "v1"),
        (1, "v1"),
        (2, "v2")
    ])
    def test_dispatch_to_correct_version(self, request, factory, version, mock_to_call):
        minimal_config = {}
        if version:
            minimal_config["version"] = version
        factory(NAME, IMAGE, minimal_config, TEAMS, TAGS, DEPLOYMENT_ID)
        mock_factory = request.getfuncargvalue(mock_to_call)
        mock_factory.assert_called_with(NAME, IMAGE, TEAMS, TAGS, ANY, DEPLOYMENT_ID)
