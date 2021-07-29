#!/usr/bin/env python
# -*- coding: utf-8

# Copyright 2017-2021 The FIAAS Authors
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
import copy

import mock
import pytest
from k8s.models.deployment import Deployment, DeploymentSpec
from k8s.models.pod import Container, PodSpec, PodTemplateSpec, EnvVar
from requests import Response, Session, HTTPError

from fiaas_deploy_daemon import Configuration
from fiaas_deploy_daemon.extension_hook_caller import ExtensionHookCaller

URL_PARAM = "URL"


class Object(object):
    pass


class TestExtensionHookCaller(object):

    @pytest.fixture
    def session_respond_500(self):
        mock_session = mock.create_autospec(Session)
        mock_session.post.return_value = self.response_other(500)
        return mock_session

    @pytest.fixture
    def session_respond_404(self):
        mock_session = mock.create_autospec(Session)
        mock_session.post.return_value = self.response_other(404)
        return mock_session

    @pytest.fixture
    def session_respond_200(self):
        mock_session = mock.create_autospec(Session)
        data = self.deployment_v2()
        mock_session.post.return_value = self.response_200(data)
        return mock_session

    @pytest.fixture
    def session(self):
        return mock.create_autospec(Session)

    def deployment_v2(self):
        main_container = Container(env=[EnvVar(name="DUMMY", value="CANARY")])
        sidecar = Container(env=[EnvVar(name="SIDECAR", value="CANARY")])
        pod_spec = PodSpec(containers=[main_container, sidecar])
        pod_template_spec = PodTemplateSpec(spec=pod_spec)
        deployment_spec = DeploymentSpec(template=pod_template_spec)
        data = Deployment(spec=deployment_spec)
        return data.as_dict()

    @pytest.fixture
    def deployment(self):
        main_container = Container(env=[EnvVar(name="DUMMY", value="CANARY")])
        pod_spec = PodSpec(containers=[main_container])
        pod_template_spec = PodTemplateSpec(spec=pod_spec)
        deployment_spec = DeploymentSpec(template=pod_template_spec)
        return Deployment(spec=deployment_spec)

    @staticmethod
    def response_200(data):
        mock_response = mock.create_autospec(Response)
        mock_response.status_code = 200
        mock_response.json.return_value = data
        return mock_response

    @staticmethod
    def response_other(status):
        mock_response = mock.create_autospec(Response)
        mock_response.status_code = status
        mock_response.raise_for_status.side_effect = HTTPError
        return mock_response

    @pytest.mark.usefixtures("session_respond_404")
    def test_return_same_object_when_404_occurs(self, session_respond_404, app_spec, deployment):
        conf = Configuration(['--extension-hook-url', URL_PARAM])
        extension_hook_caller = ExtensionHookCaller(conf, session_respond_404)
        obj = copy.deepcopy(deployment)
        extension_hook_caller.apply(obj, app_spec)
        assert obj == deployment

    @pytest.mark.usefixtures("session_respond_200")
    def test_return_respone_when_200_occurs(self, session_respond_200, app_spec, deployment):
        conf = Configuration(['--extension-hook-url', URL_PARAM])
        extension_hook_caller = ExtensionHookCaller(conf, session_respond_200)
        obj = copy.deepcopy(deployment)
        expected = self.deployment_v2()
        extension_hook_caller.apply(obj, app_spec)
        assert isinstance(obj, type(deployment))
        assert obj != deployment
        assert obj.as_dict() == expected

    @pytest.mark.usefixtures("session_respond_500")
    def test_raise_exception_when_500_occurs(self, session_respond_500, app_spec, deployment):
        conf = Configuration(['--extension-hook-url', URL_PARAM])
        extension_hook_caller = ExtensionHookCaller(conf, session_respond_500)
        obj = copy.deepcopy(deployment)
        with pytest.raises(HTTPError):
            extension_hook_caller.apply(obj, app_spec)

    @pytest.mark.usefixtures("session_respond_404")
    def test_return_same_object_when_no_url_in_config(self, session, app_spec, deployment):
        conf = Configuration()
        extension_hook_caller = ExtensionHookCaller(conf, session)
        obj = copy.deepcopy(deployment)
        extension_hook_caller.apply(obj, app_spec)
        assert obj == deployment
        session.post.assert_not_called()
