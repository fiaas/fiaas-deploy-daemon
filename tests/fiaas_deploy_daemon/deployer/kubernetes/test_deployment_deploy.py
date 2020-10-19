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
from collections import defaultdict

import mock
import pytest
from k8s.models.deployment import Deployment
from mock import create_autospec
from requests import Response

from fiaas_deploy_daemon.config import Configuration
from fiaas_deploy_daemon.deployer.kubernetes.deployment import DeploymentDeployer, DataDog, Prometheus, Secrets
from fiaas_deploy_daemon.deployer.kubernetes.deployment.deployer import _make_probe
from fiaas_deploy_daemon.specs.models import CheckSpec, HttpCheckSpec, TcpCheckSpec, AutoscalerSpec, \
    ResourceRequirementSpec, ResourcesSpec, ExecCheckSpec, HealthCheckSpec, LabelAndAnnotationSpec
from fiaas_deploy_daemon.tools import merge_dicts

from utils import TypeMatcher

SELECTOR = {'app': 'testapp'}
LABELS = {"deployment_deployer": "pass through", "global_label": "impossible to override"}
DEPLOYMENTS_URI = '/apis/apps/v1/namespaces/default/deployments/'


def test_make_http_probe():
    check_spec = CheckSpec(http=HttpCheckSpec(path="/", port=8080,
                                              http_headers={"Authorization": "ZmlubjpqdXN0aW5iaWViZXJfeG94bw=="}),
                           tcp=None, execute=None, initial_delay_seconds=30, period_seconds=60, success_threshold=3,
                           failure_threshold=3, timeout_seconds=10)
    probe = _make_probe(check_spec)
    assert probe.httpGet.path == "/"
    assert probe.httpGet.port == 8080
    assert probe.httpGet.scheme == "HTTP"
    assert len(probe.httpGet.httpHeaders) == 1
    assert probe.httpGet.httpHeaders[0].name == "Authorization"
    assert probe.httpGet.httpHeaders[0].value == "ZmlubjpqdXN0aW5iaWViZXJfeG94bw=="
    assert probe.initialDelaySeconds == 30
    assert probe.periodSeconds == 60
    assert probe.successThreshold == 3
    assert probe.timeoutSeconds == 10


def test_make_tcp_probe():
    check_spec = CheckSpec(tcp=TcpCheckSpec(port=31337), http=None, execute=None, initial_delay_seconds=30,
                           period_seconds=60, success_threshold=3, failure_threshold=3, timeout_seconds=10)
    probe = _make_probe(check_spec)
    assert probe.tcpSocket.port == 31337
    assert probe.initialDelaySeconds == 30
    assert probe.periodSeconds == 60
    assert probe.successThreshold == 3
    assert probe.timeoutSeconds == 10


def test_make_probe_should_fail_when_no_healthcheck_is_defined():
    check_spec = CheckSpec(tcp=None, execute=None, http=None, initial_delay_seconds=30, period_seconds=60,
                           success_threshold=3, failure_threshold=3, timeout_seconds=10)
    with pytest.raises(RuntimeError):
        _make_probe(check_spec)


class TestDeploymentDeployer(object):
    @pytest.fixture(params=(
            None,
            "test"
    ))
    def environment(self, request):
        yield request.param

    @pytest.fixture(params=(
            ("gke", {}, True),
            ("diy", {'A_GLOBAL_DIGIT': '0.01', 'A_GLOBAL_STRING': 'test'}, True),
            ("gke", {'A_GLOBAL_DIGIT': '0.01', 'A_GLOBAL_STRING': 'test', 'INFRASTRUCTURE': 'illegal',
                     'ARTIFACT_NAME': 'illegal'}, False),
    ))
    def config(self, request, environment):
        infra, global_env, use_in_memory_emptydirs = request.param
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.infrastructure = infra
        config.environment = environment
        config.global_env = global_env
        config.pre_stop_delay = 1
        config.log_format = "json"
        config.use_in_memory_emptydirs = use_in_memory_emptydirs
        config.deployment_max_surge = u"25%"
        config.deployment_max_unavailable = 0
        yield config

    @pytest.fixture(params=(
            (True, {"foo": "bar", "global_label": "attempt to override"}, {"bar": "baz"},
             {"bar": "foo", "global_label": "attempt to override"}, {"quux": "bax"}, False),
            (True, {}, {"bar": "baz"}, {"foo": "bar"}, {}, False),
            (True, {"foo": "bar"}, {}, {}, {"bar": "baz"}, True,),
            (False, {}, {}, {}, {}, True),
            (False, {}, {}, {}, {}, True),
    ))
    def app_spec(self, request, app_spec):
        generic_toggle, deploy_labels, deploy_annotations, pod_labels, pod_annotations, singleton = request.param

        labels = LabelAndAnnotationSpec(deployment=deploy_labels, horizontal_pod_autoscaler={}, ingress={},
                                        service={}, pod=pod_labels, status={})
        annotations = LabelAndAnnotationSpec(deployment=deploy_annotations, horizontal_pod_autoscaler={}, ingress={},
                                             service={}, pod=pod_annotations, status={})

        if generic_toggle:
            ports = app_spec.ports
            health_checks = app_spec.health_checks
            replicas = 1
        else:
            ports = []
            exec_check = CheckSpec(http=None, tcp=None, execute=ExecCheckSpec(command="/app/check.sh"),
                                   initial_delay_seconds=10, period_seconds=10, success_threshold=1,
                                   failure_threshold=3, timeout_seconds=1)
            health_checks = HealthCheckSpec(liveness=exec_check, readiness=exec_check)
            replicas = 5

        yield app_spec._replace(
            admin_access=generic_toggle,
            ports=ports,
            health_checks=health_checks,
            labels=labels,
            annotations=annotations,
            replicas=replicas,
            singleton=singleton,
        )

    @pytest.fixture
    def datadog(self, config):
        return mock.create_autospec(DataDog(config), spec_set=True, instance=True)

    @pytest.fixture
    def prometheus(self):
        return mock.create_autospec(Prometheus(), spec_set=True, instance=True)

    @pytest.fixture
    def secrets(self, config):
        return mock.create_autospec(Secrets(config, None, None), spec_set=True, instance=True)

    @pytest.mark.usefixtures("get")
    def test_deploy_new_deployment(self, post, config, app_spec, datadog, prometheus, secrets, owner_references):
        expected_deployment = create_expected_deployment(config, app_spec)
        mock_response = create_autospec(Response)
        mock_response.json.return_value = expected_deployment
        post.side_effect = None
        post.return_value = mock_response

        deployer = DeploymentDeployer(config, datadog, prometheus, secrets, owner_references)
        deployer.deploy(app_spec, SELECTOR, LABELS, False)

        pytest.helpers.assert_any_call(post, DEPLOYMENTS_URI, expected_deployment)
        datadog.apply.assert_called_once_with(TypeMatcher(Deployment), app_spec, False)
        prometheus.apply.assert_called_once_with(TypeMatcher(Deployment), app_spec)
        secrets.apply.assert_called_once_with(TypeMatcher(Deployment), app_spec)
        owner_references.apply.assert_called_with(TypeMatcher(Deployment), app_spec)

    def test_deploy_clears_alpha_beta_annotations(self, put, get, config, app_spec, datadog, prometheus, secrets, owner_references):
        old_strongbox_spec = app_spec.strongbox._replace(enabled=True, groups=["group1", "group2"])
        old_app_spec = app_spec._replace(replicas=10, strongbox=old_strongbox_spec)
        old_deployment = create_expected_deployment(config, old_app_spec, add_init_container_annotations=True)
        get_mock_response = create_autospec(Response)
        get_mock_response.json.return_value = old_deployment
        get.side_effect = None
        get.return_value = get_mock_response

        expected_deployment = create_expected_deployment(config, app_spec)
        put_mock_response = create_autospec(Response)
        put_mock_response.json.return_value = expected_deployment
        put.side_effect = None
        put.return_value = put_mock_response

        deployer = DeploymentDeployer(config, datadog, prometheus, secrets, owner_references)
        deployer.deploy(app_spec, SELECTOR, LABELS, False)

        pytest.helpers.assert_any_call(put, DEPLOYMENTS_URI + "testapp", expected_deployment)
        datadog.apply.assert_called_once_with(DeploymentMatcher(), app_spec, False)
        prometheus.apply.assert_called_once_with(DeploymentMatcher(), app_spec)
        secrets.apply.assert_called_once_with(DeploymentMatcher(), app_spec)

    @pytest.mark.parametrize("previous_replicas,max_replicas,min_replicas,cpu_request,expected_replicas", (
            (5, 3, 2, None, 3),
            (5, 3, 2, "1", 5),
            (0, 3, 2, "1", 3),
    ))
    def test_replicas_when_autoscaler_enabled(self, previous_replicas, max_replicas, min_replicas, cpu_request,
                                              expected_replicas, config, app_spec, get, put, post, datadog, prometheus,
                                              secrets, owner_references):
        deployer = DeploymentDeployer(config, datadog, prometheus, secrets, owner_references)

        image = "finntech/testimage:version2"
        version = "version2"
        app_spec = app_spec._replace(
            replicas=max_replicas,
            autoscaler=AutoscalerSpec(enabled=True, min_replicas=min_replicas, cpu_threshold_percentage=50),
            image=image)
        if cpu_request:
            app_spec = app_spec._replace(
                resources=ResourcesSpec(
                    requests=ResourceRequirementSpec(cpu=cpu_request, memory=None),
                    limits=ResourceRequirementSpec(cpu=None, memory=None)))

        expected_volumes = _get_expected_volumes(app_spec)
        expected_volume_mounts = _get_expected_volume_mounts(app_spec)

        mock_response = create_autospec(Response)
        mock_response.json.return_value = {
            'metadata': pytest.helpers.create_metadata('testapp', labels=LABELS),
            'spec': {
                'selector': {'matchLabels': SELECTOR},
                'template': {
                    'spec': {
                        'dnsPolicy': 'ClusterFirst',
                        'automountServiceAccountToken': False,
                        'serviceAccountName': 'default',
                        'terminationGracePeriodSeconds': 31,
                        'restartPolicy': 'Always',
                        'volumes': expected_volumes,
                        'imagePullSecrets': [],
                        'strategy': {
                            'type': 'rollingUpdate',
                            'rollingUpdate': {
                                'maxSurge': '25%',
                                'maxUnavailable': 0
                            },
                        },
                        'containers': [{
                            'livenessProbe': {
                                'initialDelaySeconds': 10,
                                'periodSeconds': 10,
                                'successThreshold': 1,
                                'failureThreshold': 3,
                                'timeoutSeconds': 1,
                                'tcpSocket': {
                                    'port': 8080
                                }
                            },
                            'name': 'testapp',
                            'image': 'finntech/testimage:version',
                            'volumeMounts': expected_volume_mounts,
                            'command': [],
                            'args': [],
                            'env': create_environment_variables(config.infrastructure,
                                                                global_env=config.global_env,
                                                                environment=config.environment),
                            'envFrom': [{
                                'configMapRef': {
                                    'name': app_spec.name,
                                    'optional': True,
                                }
                            }],
                            'imagePullPolicy': 'IfNotPresent',
                            'readinessProbe': {
                                'initialDelaySeconds': 10,
                                'periodSeconds': 10,
                                'successThreshold': 1,
                                'failureThreshold': 3,
                                'timeoutSeconds': 1,
                                'httpGet': {
                                    'path': '/',
                                    'scheme': 'HTTP',
                                    'port': 8080,
                                    'httpHeaders': []
                                }
                            },
                            'ports': [{'protocol': 'TCP', 'containerPort': 8080, 'name': 'http'}],
                            'resources': {}
                        }]
                    },
                    'metadata': pytest.helpers.create_metadata('testapp', labels=LABELS)
                },
                'replicas': previous_replicas,
                'revisionHistoryLimit': 5
            }
        }
        get.side_effect = None
        get.return_value = mock_response

        expected_deployment = create_expected_deployment(config, app_spec, image=image, version=version,
                                                         replicas=expected_replicas)
        put_mock_response = create_autospec(Response)
        put_mock_response.json.return_value = expected_deployment
        put.side_effect = None
        put.return_value = put_mock_response

        deployer.deploy(app_spec, SELECTOR, LABELS, False)

        pytest.helpers.assert_no_calls(post)
        pytest.helpers.assert_any_call(put, DEPLOYMENTS_URI + "testapp", expected_deployment)
        datadog.apply.assert_called_once_with(DeploymentMatcher(), app_spec, False)
        prometheus.apply.assert_called_once_with(DeploymentMatcher(), app_spec)
        secrets.apply.assert_called_once_with(DeploymentMatcher(), app_spec)


def create_expected_deployment(config,
                               app_spec,
                               image='finntech/testimage:version',
                               version="version",
                               replicas=None,
                               add_init_container_annotations=False):
    expected_volumes = _get_expected_volumes(app_spec, config.use_in_memory_emptydirs)
    expected_volume_mounts = _get_expected_volume_mounts(app_spec)

    base_expected_health_check = {
        'initialDelaySeconds': 10,
        'periodSeconds': 10,
        'successThreshold': 1,
        'failureThreshold': 3,
        'timeoutSeconds': 1,
    }
    if app_spec.ports:
        expected_liveness_check = merge_dicts(base_expected_health_check, {
            'tcpSocket': {
                'port': 8080
            }
        })
        expected_readiness_check = merge_dicts(base_expected_health_check, {
            'httpGet': {
                'path': '/',
                'scheme': 'HTTP',
                'port': 8080,
                'httpHeaders': []
            }
        })
    else:
        exec_check = merge_dicts(base_expected_health_check, {
            'exec': {
                'command': ['/app/check.sh'],
            }
        })
        expected_liveness_check = exec_check
        expected_readiness_check = exec_check

    expected_env_from = [{
        'configMapRef': {
            'name': app_spec.name,
            'optional': True,
        }
    }]

    resources = defaultdict(dict)
    if app_spec.resources.limits.cpu:
        resources["limits"]["cpu"] = app_spec.resources.limits.cpu
    if app_spec.resources.limits.memory:
        resources["limits"]["memory"] = app_spec.resources.limits.memory
    if app_spec.resources.requests.cpu:
        resources["requests"]["cpu"] = app_spec.resources.requests.cpu
    if app_spec.resources.requests.memory:
        resources["requests"]["memory"] = app_spec.resources.requests.memory
    resources = dict(resources)

    containers = [{
        'livenessProbe': expected_liveness_check,
        'name': app_spec.name,
        'image': image,
        'volumeMounts': expected_volume_mounts,
        'lifecycle': {
            'preStop': {
                'exec': {
                    'command': ['sleep', '1']
                }
            }
        },
        'command': [],
        'args': [],
        'env': create_environment_variables(config.infrastructure, global_env=config.global_env,
                                            version=version, environment=config.environment),
        'envFrom': expected_env_from,
        'imagePullPolicy': 'IfNotPresent',
        'readinessProbe': expected_readiness_check,
        'ports': [{'protocol': 'TCP', 'containerPort': 8080, 'name': 'http'}] if app_spec.ports else [],
        'resources': resources,
    }]
    deployment_annotations = app_spec.annotations.deployment if app_spec.annotations.deployment else None

    pod_annotations = app_spec.annotations.pod if app_spec.annotations.pod else {}
    init_container_annotations = {
        "pod.alpha.kubernetes.io/init-containers": 'some data',
        "pod.beta.kubernetes.io/init-containers": 'some data'
    } if add_init_container_annotations else {}
    pod_annotations = _none_if_empty(merge_dicts(pod_annotations, init_container_annotations))

    max_surge = u"25%"
    max_unavailable = 0
    if app_spec.replicas == 1 and app_spec.singleton:
        max_surge = 0
        max_unavailable = 1

    deployment = {
        'metadata': pytest.helpers.create_metadata(app_spec.name,
                                                   labels=merge_dicts(app_spec.labels.deployment, LABELS),
                                                   annotations=deployment_annotations),
        'spec': {
            'selector': {'matchLabels': SELECTOR},
            'template': {
                'spec': {
                    'dnsPolicy': 'ClusterFirst',
                    'automountServiceAccountToken': app_spec.admin_access,
                    'serviceAccountName': "default",
                    'terminationGracePeriodSeconds': 31,
                    'restartPolicy': 'Always',
                    'volumes': expected_volumes,
                    'imagePullSecrets': [],
                    'containers': containers,
                    'initContainers': []
                },
                'metadata': pytest.helpers.create_metadata(app_spec.name,
                                                           labels=_get_expected_template_labels(app_spec.labels.pod),
                                                           annotations=pod_annotations)
            },
            'replicas': replicas if replicas else app_spec.replicas,
            'revisionHistoryLimit': 5,
            'strategy': {
                'type': 'RollingUpdate',
                'rollingUpdate': {
                    'maxSurge': max_surge,
                    'maxUnavailable': max_unavailable
                }
            }
        }
    }
    return deployment


def create_environment_variables(infrastructure, global_env=None, version="version", environment=None):
    env = [
        {'name': 'ARTIFACT_NAME', 'value': 'testapp'},
        {'name': 'LOG_STDOUT', 'value': 'true'},
        {'name': 'VERSION', 'value': version},
        {'name': 'FIAAS_INFRASTRUCTURE', 'value': infrastructure},
        {'name': 'LOG_FORMAT', 'value': 'json'},
        {'name': 'IMAGE', 'value': 'finntech/testimage:' + version},
        {'name': 'CONSTRETTO_TAGS', 'value': _create_constretto_tag(environment)},
    ]
    if environment:
        env.extend([
            {'name': 'FIAAS_ENVIRONMENT', 'value': environment},
            {'name': 'FINN_ENV', 'value': environment},
        ])
    if global_env:
        env.append({'name': 'A_GLOBAL_STRING', 'value': global_env['A_GLOBAL_STRING']})
        env.append({'name': 'FIAAS_A_GLOBAL_STRING', 'value': global_env['A_GLOBAL_STRING']})
        env.append({'name': 'A_GLOBAL_DIGIT', 'value': global_env['A_GLOBAL_DIGIT']})
        env.append({'name': 'FIAAS_A_GLOBAL_DIGIT', 'value': global_env['A_GLOBAL_DIGIT']})

    env.append({'name': 'FIAAS_REQUESTS_CPU', 'valueFrom': {'resourceFieldRef': {
        'containerName': 'testapp', 'resource': 'requests.cpu', 'divisor': 1}}})
    env.append({'name': 'FIAAS_REQUESTS_MEMORY', 'valueFrom': {'resourceFieldRef': {
        'containerName': 'testapp', 'resource': 'requests.memory', 'divisor': 1}}})
    env.append({'name': 'FIAAS_LIMITS_CPU', 'valueFrom': {'resourceFieldRef': {
        'containerName': 'testapp', 'resource': 'limits.cpu', 'divisor': 1}}})
    env.append({'name': 'FIAAS_LIMITS_MEMORY', 'valueFrom': {'resourceFieldRef': {
        'containerName': 'testapp', 'resource': 'limits.memory', 'divisor': 1}}})
    env.append({'name': 'FIAAS_NAMESPACE', 'valueFrom': {'fieldRef': {'fieldPath': 'metadata.namespace'}}})
    env.append({'name': 'FIAAS_POD_NAME', 'valueFrom': {'fieldRef': {'fieldPath': 'metadata.name'}}})

    env.sort(key=lambda x: x["name"])
    return env


def _create_constretto_tag(environment):
    if environment:
        return 'kubernetes-{},kubernetes,{}'.format(environment, environment)
    return 'kubernetes'


def _get_expected_template_labels(custom_labels):
    return merge_dicts(custom_labels, {"fiaas/status": "active"}, LABELS)


def _get_expected_volumes(app_spec, use_in_memory_emptydirs=False):
    config_map_volume = {
        'name': "{}-config".format(app_spec.name),
        'configMap': {
            'name': app_spec.name,
            'optional': True
        }
    }
    tmp_volume = {
        'name': "tmp"
    }
    if use_in_memory_emptydirs:
        tmp_volume["emptyDir"] = {'medium': "Memory"}
    return [config_map_volume, tmp_volume]


def _get_expected_volume_mounts(app_spec):
    config_map_volume_mount = {
        'name': "{}-config".format(app_spec.name),
        'readOnly': True,
        'mountPath': '/var/run/config/fiaas/'
    }
    tmp_volume_mount = {
        'name': "tmp",
        'readOnly': False,
        'mountPath': "/tmp"
    }
    return [config_map_volume_mount, tmp_volume_mount]


def _none_if_empty(thing):
    return thing if thing else None


class DeploymentMatcher(object):
    def __eq__(self, other):
        return isinstance(other, Deployment)
