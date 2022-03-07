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
import mock
from mock import create_autospec
from requests import Response

from k8s.models.service_account import ServiceAccount
from k8s.models.common import ObjectMeta
from k8s.client import NotFound

from fiaas_deploy_daemon.config import Configuration
from fiaas_deploy_daemon.deployer.kubernetes.service_account import ServiceAccountDeployer
from utils import TypeMatcher

from fiaas_deploy_daemon.deployer.kubernetes.owner_references import OwnerReferences

SERVICE_ACCOUNT_URI = '/api/v1/namespaces/default/serviceaccounts/'
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

        pytest.helpers.assert_any_call(post, SERVICE_ACCOUNT_URI, expected_service_account)
        owner_references.apply.assert_called_once_with(TypeMatcher(ServiceAccount), app_spec)

    @pytest.mark.parametrize('owner_references', (
        [],
        [{
                "apiVersion": "example.com/v1",
                "kind": "random",
                "name": "testapp",
        }],
        [
            {
                "apiVersion": "example.com/v1",
                "kind": "random",
                "name": "testapp",
            },
            {
                "apiVersion": "example.com/v1",
                "kind": "random2",
                "name": "testapp",
            },
        ],
    ))
    def test_deploy_existing_service_account(self, get, deployer, post, put, app_spec, owner_references):
        existing_service_account = {
                'metadata': pytest.helpers.create_metadata('testapp', labels=LABELS, owner_references=owner_references),
                'secrets': [],
                'imagePullSecrets': []
        }

        mock_response = create_autospec(Response)
        mock_response.json.return_value = existing_service_account
        get.side_effect = None
        get.return_value = mock_response

        deployer.deploy(app_spec, LABELS)
        put.assert_not_called()
        post.assert_not_called()

    def test_deploy_existing_fiaas_owned_service_account(self, get, post, put, app_spec):
        existing_service_account = {
            'metadata': pytest.helpers.create_metadata(
                app_spec.name,
                labels=LABELS,
                owner_references=[{
                    "apiVersion": "fiaas.schibsted.io/v1",
                    "blockOwnerDeletion": True,
                    "controller": True,
                    "kind": "Application",
                    "name": app_spec.name,
                    "uid": app_spec.uid,
                }],
            ),
            'secrets': [{'name': app_spec.name + "-token-6f7fp"}],
            'imagePullSecrets': []
        }

        def get_existing_or_not(uri):
            mock_response = create_autospec(Response)
            mock_response.json.return_value = existing_service_account
            if uri == SERVICE_ACCOUNT_URI + app_spec.name:
                return mock_response
            else:
                raise NotFound

        get.side_effect = get_existing_or_not

        mock_response = create_autospec(Response)
        mock_response.json.return_value = existing_service_account
        put.return_value = mock_response

        config = create_autospec(Configuration([]), spec_set=True)
        deployer = ServiceAccountDeployer(config, OwnerReferences())

        deployer.deploy(app_spec, LABELS)
        post.assert_not_called()
        pytest.helpers.assert_any_call(put, SERVICE_ACCOUNT_URI + app_spec.name, existing_service_account)

    @pytest.fixture
    def service_account_get(self):
        with mock.patch('k8s.models.service_account.ServiceAccount.get') as get:
            yield get

    @pytest.mark.parametrize('default_sa_exists,image_pull_secrets', (
        (False, []),
        (True, []),
        (True, ['one']),
        (True, ['one', 'two', 'three']),
    ))
    def test_service_account_should_propagate_image_pull_secrets_from_default(self, service_account_get, post,
                                                                              app_spec, owner_references, deployer,
                                                                              default_sa_exists, image_pull_secrets):
        default_sa_name = 'default'
        default_service_account = ServiceAccount(
            metadata=ObjectMeta(name=default_sa_name),
            imagePullSecrets=image_pull_secrets,
        )

        def get_default_or_notfound(name, namespace):
            if name == default_sa_name and default_sa_exists:
                return default_service_account
            else:
                raise NotFound

        service_account_get.side_effect = get_default_or_notfound

        expected_service_account = {
            'metadata': pytest.helpers.create_metadata('testapp', labels=LABELS),
            'secrets': [],
            'imagePullSecrets': image_pull_secrets,
        }
        mock_response = create_autospec(Response)
        mock_response.json.return_value = expected_service_account
        post.return_value = mock_response

        deployer.deploy(app_spec, LABELS)

        pytest.helpers.assert_any_call(post, SERVICE_ACCOUNT_URI, expected_service_account)
        owner_references.apply.assert_called_once_with(TypeMatcher(ServiceAccount), app_spec)
