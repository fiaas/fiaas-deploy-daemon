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
from copy import deepcopy

import mock
import pytest
from k8s.models.deployment import Deployment, DeploymentSpec
from k8s.models.pod import PodTemplateSpec, PodSpec, Container, EnvVar

from fiaas_deploy_daemon import Configuration
from fiaas_deploy_daemon.deployer.kubernetes.deployment import DataDog

CONTAINER_IMAGE = "datadog_container_image:tag"
CONTAINER_IMAGE_LATEST = "datadog_container_image:latest"


class TestDataDog(object):
    @pytest.fixture(scope="module")
    def config(self):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.datadog_container_image = CONTAINER_IMAGE
        config.datadog_container_memory = "2Gi"
        config.datadog_global_tags = {"tag": "test"}
        config.datadog_activate_sleep = False
        return config

    @pytest.fixture(scope="module")
    def datadog(self, config):
        return DataDog(config)

    @pytest.fixture
    def deployment(self):
        main_container = Container(env=[EnvVar(name="DUMMY", value="CANARY")])
        pod_spec = PodSpec(containers=[main_container])
        pod_template_spec = PodTemplateSpec(spec=pod_spec)
        deployment_spec = DeploymentSpec(template=pod_template_spec)
        return Deployment(spec=deployment_spec)

    @pytest.fixture(params=(True, False))
    def best_effort_required(self, request):
        yield request.param

    def test_noop_when_not_enabled(self, datadog, app_spec, deployment):
        expected = deepcopy(deployment)
        datadog.apply(deployment, app_spec, False, 0)
        assert expected == deployment

    @pytest.mark.parametrize("best_effort_required", (False, True))
    def test_adds_env_when_enabled(self, datadog, app_spec, deployment, best_effort_required):
        datadog_spec = app_spec.datadog._replace(enabled=True, tags={})
        app_spec = app_spec._replace(datadog=datadog_spec)
        datadog.apply(deployment, app_spec, best_effort_required, 0)
        expected = [
            {"name": "DUMMY", "value": "CANARY"},
            {"name": "STATSD_HOST", "value": "localhost"},
            {"name": "STATSD_PORT", "value": "8125"}
        ]
        assert expected == deployment.as_dict()["spec"]["template"]["spec"]["containers"][0]["env"]

    def test_adds_global_tags_when_enabled(self, datadog, app_spec, deployment, best_effort_required):
        datadog_spec = app_spec.datadog._replace(enabled=True, tags={})
        app_spec = app_spec._replace(datadog=datadog_spec)
        datadog.apply(deployment, app_spec, best_effort_required, 0)
        expected = {
                    'name': 'DD_TAGS',
                    'value': "app:{},k8s_namespace:{},tag:test".format(app_spec.name, app_spec.namespace)
                }
        assert expected in deployment.as_dict()["spec"]["template"]["spec"]["containers"][1]["env"]

    @pytest.mark.parametrize("name, namespace", (
        ("bilbo", "baggins"),
        ("rincewind", "discworld")
    ))
    def test_adds_container_when_enabled(self, datadog, app_spec, deployment, best_effort_required, name, namespace):
        datadog_spec = app_spec.datadog._replace(
            enabled=True,
            tags={"a": "1", "b": "2"}
        )
        app_spec = app_spec._replace(datadog=datadog_spec)
        app_spec = app_spec._replace(datadog=datadog_spec)
        app_spec = app_spec._replace(name=name, namespace=namespace)
        datadog.apply(deployment, app_spec, best_effort_required, 0)
        expected = {
            'name': DataDog.DATADOG_CONTAINER_NAME,
            'image': CONTAINER_IMAGE,
            'volumeMounts': [],
            'command': [],
            'args': [],
            'env': [
                {
                    'name': 'DD_TAGS',
                    'value': "a:1,app:{},b:2,k8s_namespace:{},tag:test".format(app_spec.name, app_spec.namespace)
                },
                {'name': 'DD_API_KEY', 'valueFrom': {'secretKeyRef': {'name': 'datadog', 'key': 'apikey'}}},
                {'name': 'NON_LOCAL_TRAFFIC', 'value': 'false'},
                {'name': 'DD_LOGS_STDOUT', 'value': 'yes'},
                {'name': 'DD_EXPVAR_PORT', 'value': '42622'},
                {'name': 'DD_CMD_PORT', 'value': '42623'},
            ],
            'envFrom': [],
            'imagePullPolicy': 'IfNotPresent',
            'ports': []
        }
        if not best_effort_required:
            expected["resources"] = {
                'limits': {'cpu': '400m', 'memory': '2Gi'},
                'requests': {'cpu': '200m', 'memory': '2Gi'}
            }
        assert expected == deployment.as_dict()["spec"]["template"]["spec"]["containers"][-1]

    def test_adds_correct_image_pull_policy_for_latest(self, config, app_spec, deployment):
        config.datadog_container_image = CONTAINER_IMAGE_LATEST
        datadog = DataDog(config)

        datadog_spec = app_spec.datadog._replace(
            enabled=True
        )
        app_spec = app_spec._replace(datadog=datadog_spec)

        datadog.apply(deployment, app_spec, False, 0)

        actual = deployment.as_dict()["spec"]["template"]["spec"]["containers"][-1]
        assert actual['image'] == CONTAINER_IMAGE_LATEST
        assert actual['imagePullPolicy'] == "Always"

    def test_adds_lifecycle_when_pre_stop_delay_is_set_and_sleep_is_active(self, config, app_spec, deployment):
        config.datadog_container_image = CONTAINER_IMAGE_LATEST
        config.datadog_activate_sleep = True
        datadog = DataDog(config)

        datadog_spec = app_spec.datadog._replace(
            enabled=True
        )
        app_spec = app_spec._replace(datadog=datadog_spec)

        datadog.apply(deployment, app_spec, False, 5)

        expected = {
            'preStop': {
                'exec': {
                    'command': ['sleep', '5']
                }
            }
        }

        assert expected == deployment.as_dict()["spec"]["template"]["spec"]["containers"][-1]["lifecycle"]

    def test_does_not_add_lifecycle_when_pre_stop_delay_is_set_and_sleep_is_not_active(self, config, app_spec, deployment):
        config.datadog_container_image = CONTAINER_IMAGE_LATEST
        datadog = DataDog(config)

        datadog_spec = app_spec.datadog._replace(
            enabled=True
        )
        app_spec = app_spec._replace(datadog=datadog_spec)

        datadog.apply(deployment, app_spec, False, 5)

        assert False == ("lifecycle" in deployment.as_dict()["spec"]["template"]["spec"]["containers"][-1])
