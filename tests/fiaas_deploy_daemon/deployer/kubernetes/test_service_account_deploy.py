#!/usr/bin/env python
# -*- coding: utf-8

# Copyright 2017-2020 The FIAAS Authors
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
from mock import create_autospec
from requests import Response

from k8s.models.service_account import ServiceAccount

from fiaas_deploy_daemon.config import Configuration
from fiaas_deploy_daemon.deployer.kubernetes.service_account import ServiceAccountDeployer
from utils import TypeMatcher

SERVICES_ACCOUNT_URI = '/api/v1/namespaces/default/serviceaccounts/'
LABELS = {"service": "pass through"}


class TestServiceAccountDeployer(object):

    @pytest.fixture
    def deployer(self, owner_references):
        config = create_autospec(Configuration([]), spec_set=True)
        return ServiceAccountDeployer(config, owner_references)

    @pytest.mark.usefixtures("get")
    def test_deploy_new_service_account(self, deployer, post, app_spec, owner_references):
        expected_service_account = {
                'metadata': pytest.helpers.create_metadata('testapp', labels=LABELS),
                'secrets': [],
                'imagePullSecrets': []
        }

        mock_response = create_autospec(Response)
        mock_response.json.return_value = expected_service_account
        post.return_value = mock_response

        deployer.deploy(app_spec, LABELS)

        pytest.helpers.assert_any_call(post, SERVICES_ACCOUNT_URI, expected_service_account)
        owner_references.apply.assert_called_once_with(TypeMatcher(ServiceAccount), app_spec)
