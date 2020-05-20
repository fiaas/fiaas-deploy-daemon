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
from mock import ANY, create_autospec

from fiaas_deploy_daemon import Configuration
from fiaas_deploy_daemon.specs.factory import SpecFactory, InvalidConfiguration, BaseFactory, BaseTransformer

IMAGE = u"finntech/docker-image:some-version"
NAME = u"application-name"
TEAMS = "IO"
TAGS = "Foo"
DEPLOYMENT_ID = "deployment_id"
NAMESPACE = "namespace"
UID = "c1f34517-6f54-11ea-8eaf-0ad3d9992c8c"


class TestSpecFactory(object):
    @pytest.fixture
    def v1(self):
        return create_autospec(BaseTransformer, spec_set=True, return_value={"version": 2})

    @pytest.fixture
    def v2(self):
        return create_autospec(BaseTransformer, spec_set=True, return_value={"version": 3})

    @pytest.fixture
    def v3(self, app_spec):
        return create_autospec(BaseFactory, spec_set=True, version=3, return_value=app_spec)

    @pytest.fixture
    def transformers(self, v1, v2):
        return {1: v1, 2: v2}

    @pytest.fixture
    def config(self):
        config = create_autospec(Configuration([]), spec_set=True)
        config.datadog_container_image = None
        return config

    @pytest.fixture
    def factory(self, v3, transformers, config):
        return SpecFactory(v3, transformers, config)

    @pytest.mark.parametrize("version,mock_to_call", [
        (None, "v1"),
        (1, "v1"),
        (2, "v2"),
    ])
    def test_dispatch_to_correct_transformer(self, request, factory, version, mock_to_call):
        minimal_config = {}
        if version:
            minimal_config["version"] = version
        factory(UID, NAME, IMAGE, minimal_config, TEAMS, TAGS, DEPLOYMENT_ID, NAMESPACE, None, None)
        mock_factory = request.getfuncargvalue(mock_to_call)
        mock_factory.assert_called_with(minimal_config, strip_defaults=False)

    @pytest.mark.parametrize("version", [1, 2, 3])
    def test_parsed_by_current_version(self, factory, version, v3):
        factory(UID, NAME, IMAGE, {"version": version}, TEAMS, TAGS, DEPLOYMENT_ID, NAMESPACE, None, None)
        v3.assert_called_with(UID, NAME, IMAGE, TEAMS, TAGS, ANY, DEPLOYMENT_ID, NAMESPACE, None, None)

    def test_raise_invalid_config_if_version_not_supported(self, factory):
        with pytest.raises(InvalidConfiguration):
            factory(UID, NAME, IMAGE, {"version": 999}, TEAMS, TAGS, DEPLOYMENT_ID, NAMESPACE, None, None)

    def test_raise_invalid_config_if_datadog_undefined_and_requested(self, factory, v3, app_spec):
        datadog_spec = app_spec.datadog._replace(enabled=True, tags={})
        v3.return_value = app_spec._replace(datadog=datadog_spec)
        with pytest.raises(InvalidConfiguration):
            factory(UID, NAME, IMAGE, {"version": 3}, TEAMS, TAGS, DEPLOYMENT_ID, NAMESPACE, None, None)

    def test_accept_config_if_datadog_defined_and_requested(self, factory, v3, app_spec, config):
        config.datadog_container_image = "datadog"
        datadog_spec = app_spec.datadog._replace(enabled=True, tags={})
        expected = app_spec._replace(datadog=datadog_spec)
        v3.return_value = expected
        actual = factory(UID, NAME, IMAGE, {"version": 3}, TEAMS, TAGS, DEPLOYMENT_ID, NAMESPACE, None, None)
        assert actual == expected

    @pytest.mark.parametrize("exception", (
        AttributeError,
        KeyError,
        IndexError,
        ValueError,
        TypeError,
        NameError
    ))
    def test_parse_errors_raises_invalid_config(self, factory, v3, exception):
        v3.side_effect = exception
        with pytest.raises(InvalidConfiguration):
            factory(UID, NAME, IMAGE, {"version": 3}, TEAMS, TAGS, DEPLOYMENT_ID, NAMESPACE, None, None)
