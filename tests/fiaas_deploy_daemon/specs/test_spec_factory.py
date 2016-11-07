#!/usr/bin/env python
# -*- coding: utf-8

import pytest
from mock import MagicMock, ANY

from fiaas_deploy_daemon.specs.factory import SpecFactory

IMAGE = u"finntech/docker-image:some-version"
NAME = u"application-name"


class TestSpecFactory(object):
    @pytest.fixture
    def v1(self):
        return MagicMock()

    @pytest.fixture
    def v2(self):
        return MagicMock()

    @pytest.fixture()
    def factory(self, session, v1, v2):
        return SpecFactory(session, {1: v1, 2: v2})

    @pytest.mark.parametrize("filename,mock_to_call", [
        ("v1minimal", "v1"),
        ("v2minimal", "v2")
    ])
    def test_dispatch_to_correct_version(self, request, make_url, factory, filename, mock_to_call):
        factory(NAME, IMAGE, make_url(filename))
        mock_factory = request.getfuncargvalue(mock_to_call)
        mock_factory.assert_called_with(NAME, IMAGE, ANY)
