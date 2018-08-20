#!/usr/bin/env python
# -*- coding: utf-8
from collections import defaultdict

import mock
import pytest
from k8s.models.deployment import Deployment
from mock import create_autospec
from requests import Response

from fiaas_deploy_daemon.config import Configuration
from fiaas_deploy_daemon.deployer.kubernetes.deployment import DeploymentDeployer, DataDog, Prometheus, Secrets, \
    KubernetesSecrets, GenericInitSecrets, StrongboxSecrets
from fiaas_deploy_daemon.deployer.kubernetes.deployment.deployer import _make_probe
from fiaas_deploy_daemon.specs.models import CheckSpec, HttpCheckSpec, TcpCheckSpec, AutoscalerSpec, \
    ResourceRequirementSpec, ResourcesSpec, ExecCheckSpec, HealthCheckSpec, LabelAndAnnotationSpec, StrongboxSpec
from fiaas_deploy_daemon.tools import merge_dicts

SECRET_IMAGE = "fiaas/secret_image:version"
STRONGBOX_IMAGE = 'fiaas/strongbox_image:version'

INIT_CONTAINER_NAME = 'fiaas-secrets-init-container'

SELECTOR = {'app': 'testapp'}
LABELS = {"deployment_deployer": "pass through", "global_label": "impossible to override"}
DEPLOYMENTS_URI = '/apis/extensions/v1beta1/namespaces/default/deployments/'


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
            (True, True),
            # secrets init container is default when both strongbox and secrets init container is specified
            (True, False),  # secrets init container
            (False, True),  # strongbox
            (False, False),  # kubernetes secrets
    ))
    def secrets_mode(self, request):
        yield request.param

    @pytest.fixture(params=(
            None,
            "test"
    ))
    def environment(self, request):
        yield request.param

    @pytest.fixture(params=(
            ("gke", {}),
            ("diy", {'A_GLOBAL_DIGIT': '0.01', 'A_GLOBAL_STRING': 'test'}),
            ("gke", {'A_GLOBAL_DIGIT': '0.01', 'A_GLOBAL_STRING': 'test', 'INFRASTRUCTURE': 'illegal',
                     'ARTIFACT_NAME': 'illegal'}),
    ))
    def config(self, request, secrets_mode, environment):
        secret_init_container, strongbox_init_container = secrets_mode

        infra, global_env = request.param
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.infrastructure = infra
        config.environment = environment
        config.global_env = global_env
        config.secrets_init_container_image = SECRET_IMAGE if secret_init_container else None
        config.secrets_service_account_name = "secretsmanager" if secret_init_container else None
        config.strongbox_init_container_image = STRONGBOX_IMAGE if strongbox_init_container else None
        config.pre_stop_delay = 1
        config.log_format = "json"
        yield config

    @pytest.fixture(params=(
            (True, {"foo": "bar", "global_label": "attempt to override"}, {"bar": "baz"},
             {"bar": "foo", "global_label": "attempt to override"}, {"quux": "bax"}, (), False),
            (True, {}, {"bar": "baz"}, {"foo": "bar"}, {}, (), False),
            (True, {"foo": "bar"}, {}, {}, {"bar": "baz"}, (), True,),
            (False, {}, {}, {}, {}, (), True),
            (False, {}, {}, {}, {}, ("arn:aws:iam::12345678:role/the-role-name", ["foo", "bar"]), True),
    ))
    def app_spec(self, request, app_spec):
        generic_toggle, deploy_labels, deploy_annotations, pod_labels, pod_annotations, \
            strongbox_init_container, singleton = request.param

        labels = LabelAndAnnotationSpec(deployment=deploy_labels, horizontal_pod_autoscaler={}, ingress={},
                                        service={}, pod=pod_labels)
        annotations = LabelAndAnnotationSpec(deployment=deploy_annotations, horizontal_pod_autoscaler={}, ingress={},
                                             service={}, pod=pod_annotations)

        if strongbox_init_container:
            iam_role, groups = strongbox_init_container
            strongbox = StrongboxSpec(enabled=True, iam_role=iam_role, aws_region="eu-west-1", groups=groups)
        else:
            strongbox = StrongboxSpec(enabled=False, iam_role=None, aws_region="eu-west-1", groups=None)

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
            secrets_in_environment=generic_toggle,
            labels=labels,
            annotations=annotations,
            strongbox=strongbox,
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
        return Secrets(config, KubernetesSecrets(), GenericInitSecrets(config), StrongboxSecrets(config))

    @pytest.mark.usefixtures("get")
    def test_deploy_new_deployment(self, post, config, app_spec, datadog, prometheus, secrets):
        expected_deployment = create_expected_deployment(config, app_spec)
        mock_response = create_autospec(Response)
        mock_response.json.return_value = expected_deployment
        post.side_effect = None
        post.return_value = mock_response

        deployer = DeploymentDeployer(config, datadog, prometheus, secrets)
        deployer.deploy(app_spec, SELECTOR, LABELS, False)

        pytest.helpers.assert_any_call(post, DEPLOYMENTS_URI, expected_deployment)
        datadog.apply.assert_called_once_with(DeploymentMatcher(), app_spec, False)
        prometheus.apply.assert_called_once_with(DeploymentMatcher(), app_spec)

    def test_deploy_clears_alpha_beta_annotations(self, put, get, config, app_spec, datadog, prometheus, secrets):
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

        deployer = DeploymentDeployer(config, datadog, prometheus, secrets)
        deployer.deploy(app_spec, SELECTOR, LABELS, False)

        pytest.helpers.assert_any_call(put, DEPLOYMENTS_URI + "testapp", expected_deployment)
        datadog.apply.assert_called_once_with(DeploymentMatcher(), app_spec, False)
        prometheus.apply.assert_called_once_with(DeploymentMatcher(), app_spec)

    @pytest.mark.parametrize("previous_replicas,max_replicas,min_replicas,cpu_request,expected_replicas", (
            (5, 3, 2, None, 3),
            (5, 3, 2, "1", 5),
    ))
    def test_replicas_when_autoscaler_enabled(self, previous_replicas, max_replicas, min_replicas, cpu_request,
                                              expected_replicas, config, app_spec, get, put, post, datadog, prometheus,
                                              secrets):
        deployer = DeploymentDeployer(config, datadog, prometheus, secrets)

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

        uses_secrets_init_container = bool(config.secrets_init_container_image)
        uses_strongbox_init_container = config.strongbox_init_container_image and app_spec.strongbox.enabled
        expected_volumes = _get_expected_volumes(app_spec, uses_secrets_init_container, uses_strongbox_init_container)
        _, expected_volume_mounts = _get_expected_volume_mounts(app_spec, uses_secrets_init_container,
                                                                uses_strongbox_init_container)

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
                                'maxSurge': 1,
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


def _get_secrets_init_container_info(uses_secrets_init_container, uses_strongbox_init_container,
                                     app_spec):
    expected_init_volume_mounts, expected_volume_mounts = _get_expected_volume_mounts(app_spec,
                                                                                      uses_secrets_init_container,
                                                                                      uses_strongbox_init_container)

    if uses_secrets_init_container:
        init_containers = [{
            'name': INIT_CONTAINER_NAME,
            'image': SECRET_IMAGE,
            'volumeMounts': expected_init_volume_mounts,
            'command': [],
            'env': [{'name': 'K8S_DEPLOYMENT', 'value': app_spec.name}],
            'envFrom': [{
                'configMapRef': {
                    'name': INIT_CONTAINER_NAME,
                    'optional': True,
                }
            }],
            'imagePullPolicy': 'IfNotPresent',
            'ports': []
        }]
        service_account_name = "secretsmanager"
    elif uses_strongbox_init_container:
        init_containers = [{
            'name': INIT_CONTAINER_NAME,
            'image': STRONGBOX_IMAGE,
            'volumeMounts': expected_init_volume_mounts,
            'command': [],
            'env': [
                {'name': 'K8S_DEPLOYMENT', 'value': app_spec.name},
                {'name': 'AWS_REGION', 'value': app_spec.strongbox.aws_region},
                {'name': 'SECRET_GROUPS', 'value': ','.join(app_spec.strongbox.groups)},
            ],
            'envFrom': [{
                'configMapRef': {
                    'name': INIT_CONTAINER_NAME,
                    'optional': True,
                }
            }],
            'imagePullPolicy': 'IfNotPresent',
            'ports': []
        }]
        service_account_name = "default"
    else:
        init_containers = []
        service_account_name = "default"
    return (init_containers, service_account_name)


def create_expected_deployment(config,
                               app_spec,
                               image='finntech/testimage:version',
                               version="version",
                               replicas=None,
                               add_init_container_annotations=False):
    uses_secrets_init_container = bool(config.secrets_init_container_image)
    uses_strongbox_init_container = config.strongbox_init_container_image and app_spec.strongbox.enabled
    expected_volumes = _get_expected_volumes(app_spec, uses_secrets_init_container, uses_strongbox_init_container)
    _, expected_volume_mounts = _get_expected_volume_mounts(app_spec,
                                                            uses_secrets_init_container,
                                                            uses_strongbox_init_container)

    (init_containers, service_account_name) = _get_secrets_init_container_info(uses_secrets_init_container,
                                                                               uses_strongbox_init_container,
                                                                               app_spec)

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
    if app_spec.secrets_in_environment:
        expected_env_from.append({
            'secretRef': {
                'name': app_spec.name,
                'optional': True,
            }
        })

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
    strongbox_annotations = {
        "iam.amazonaws.com/role": app_spec.strongbox.iam_role} if uses_strongbox_init_container else {}
    init_container_annotations = {
        "pod.alpha.kubernetes.io/init-containers": 'some data',
        "pod.beta.kubernetes.io/init-containers": 'some data'
    } if add_init_container_annotations else {}
    pod_annotations = _none_if_empty(merge_dicts(pod_annotations, strongbox_annotations, init_container_annotations))

    max_surge = 1
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
                    'automountServiceAccountToken': uses_secrets_init_container or app_spec.admin_access,
                    'serviceAccountName': service_account_name,
                    'terminationGracePeriodSeconds': 31,
                    'restartPolicy': 'Always',
                    'volumes': expected_volumes,
                    'imagePullSecrets': [],
                    'containers': containers,
                    'initContainers': init_containers
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


def _get_expected_volumes(app_spec, uses_secrets_init_container, uses_strongbox_init_container):
    secret_volume = {
        'name': "{}-secret".format(app_spec.name),
        'secret': {
            'secretName': app_spec.name,
            'optional': True
        }
    }
    init_secret_volume = {
        'name': "{}-secret".format(app_spec.name),
    }
    config_map_volume = {
        'name': "{}-config".format(app_spec.name),
        'configMap': {
            'name': app_spec.name,
            'optional': True
        }
    }
    init_config_map_volume = {
        'name': "{}-config".format(INIT_CONTAINER_NAME),
        'configMap': {
            'name': INIT_CONTAINER_NAME,
            'optional': True
        }
    }
    tmp_volume = {
        'name': "tmp"
    }
    if uses_secrets_init_container or uses_strongbox_init_container:
        expected_volumes = [init_secret_volume, init_config_map_volume, config_map_volume, tmp_volume]
    else:
        expected_volumes = [secret_volume, config_map_volume, tmp_volume]
    return expected_volumes


def _get_expected_volume_mounts(app_spec, uses_secrets_init_container, uses_strongbox_init_container):
    secret_volume_mount = {
        'name': "{}-secret".format(app_spec.name),
        'readOnly': True,
        'mountPath': '/var/run/secrets/fiaas/'
    }
    init_secret_volume_mount = {
        'name': "{}-secret".format(app_spec.name),
        'readOnly': False,
        'mountPath': '/var/run/secrets/fiaas/'
    }
    config_map_volume_mount = {
        'name': "{}-config".format(app_spec.name),
        'readOnly': True,
        'mountPath': '/var/run/config/fiaas/'
    }
    init_config_map_volume_mount = {
        'name': "{}-config".format(INIT_CONTAINER_NAME),
        'readOnly': True,
        'mountPath': "/var/run/config/{}/".format(INIT_CONTAINER_NAME)
    }
    tmp_volume_mount = {
        'name': "tmp",
        'readOnly': False,
        'mountPath': "/tmp"
    }
    expected_volume_mounts = [secret_volume_mount, config_map_volume_mount, tmp_volume_mount]
    if uses_secrets_init_container or uses_strongbox_init_container:
        expected_init_volume_mounts = [init_secret_volume_mount, init_config_map_volume_mount, config_map_volume_mount,
                                       tmp_volume_mount]
    else:
        expected_init_volume_mounts = []
    return expected_init_volume_mounts, expected_volume_mounts


def _none_if_empty(thing):
    return thing if thing else None


class DeploymentMatcher(object):
    def __eq__(self, other):
        return isinstance(other, Deployment)
