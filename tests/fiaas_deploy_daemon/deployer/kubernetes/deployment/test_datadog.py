#!/usr/bin/env python
# -*- coding: utf-8
from copy import deepcopy

import mock
import pytest
from k8s.models.deployment import Deployment, DeploymentSpec
from k8s.models.pod import PodTemplateSpec, PodSpec, Container, EnvVar

from fiaas_deploy_daemon import Configuration
from fiaas_deploy_daemon.deployer.kubernetes.deployment import DataDog

CONTAINER_IMAGE = "datadog_container_image:latest"


class TestDataDog(object):
    @pytest.fixture(scope="module")
    def config(self):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.datadog_container_image = CONTAINER_IMAGE
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
        datadog.apply(deployment, app_spec, False)
        assert expected == deployment

    @pytest.mark.parametrize("best_effort_required", (False, True))
    def test_adds_env_when_enabled(self, datadog, app_spec, deployment, best_effort_required):
        app_spec = app_spec._replace(datadog=True)
        datadog.apply(deployment, app_spec, best_effort_required)
        expected = [
            {"name": "DUMMY", "value": "CANARY"},
            {"name": "STATSD_HOST", "value": "localhost"},
            {"name": "STATSD_PORT", "value": "8125"}
        ]
        assert expected == deployment.as_dict()["spec"]["template"]["spec"]["containers"][0]["env"]

    def test_adds_container_when_enabled(self, datadog, app_spec, deployment, best_effort_required):
        app_spec = app_spec._replace(datadog=True)
        datadog.apply(deployment, app_spec, best_effort_required)
        expected = {
            'name': DataDog.DATADOG_CONTAINER_NAME,
            'image': CONTAINER_IMAGE,
            'volumeMounts': [],
            'command': [],
            'env': [
                {'name': 'DD_TAGS', 'value': "app:{},k8s_namespace:{}".format(app_spec.name, app_spec.namespace)},
                {'name': 'API_KEY', 'valueFrom': {'secretKeyRef': {'name': 'datadog', 'key': 'apikey'}}},
                {'name': 'NON_LOCAL_TRAFFIC', 'value': 'false'},
                {'name': 'DD_LOGS_STDOUT', 'value': 'yes'}
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
