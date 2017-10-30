#!/usr/bin/env python
# -*- coding: utf-8

import mock
import pytest
from mock import create_autospec
from requests import Response

from fiaas_deploy_daemon.config import Configuration
from fiaas_deploy_daemon.deployer.kubernetes.deployment import _make_probe, DeploymentDeployer
from fiaas_deploy_daemon.specs.models import CheckSpec, HttpCheckSpec, TcpCheckSpec, PrometheusSpec, AutoscalerSpec, \
    ResourceRequirementSpec, ResourcesSpec, ExecCheckSpec, HealthCheckSpec, LabelAndAnnotationSpec
from fiaas_deploy_daemon.tools import merge_dicts

INIT_CONTAINER_NAME = 'fiaas-secrets-init-container'

SELECTOR = {'app': 'testapp'}
LABELS = {"deployment_deployer": "pass through"}
DEPLOYMENTS_URI = '/apis/extensions/v1beta1/namespaces/default/deployments/'


def test_make_http_probe():
    check_spec = CheckSpec(http=HttpCheckSpec(path="/", port=8080,
                                              http_headers={"Authorization": "ZmlubjpqdXN0aW5iaWViZXJfeG94bw=="}),
                           tcp=None, execute=None, initial_delay_seconds=30, period_seconds=60, success_threshold=3,
                           timeout_seconds=10)
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
                           period_seconds=60, success_threshold=3, timeout_seconds=10)
    probe = _make_probe(check_spec)
    assert probe.tcpSocket.port == 31337
    assert probe.initialDelaySeconds == 30
    assert probe.periodSeconds == 60
    assert probe.successThreshold == 3
    assert probe.timeoutSeconds == 10


def test_make_probe_should_fail_when_no_healthcheck_is_defined():
    check_spec = CheckSpec(tcp=None, execute=None, http=None, initial_delay_seconds=30, period_seconds=60,
                           success_threshold=3, timeout_seconds=10)
    with pytest.raises(RuntimeError):
        _make_probe(check_spec)


class TestDeploymentDeployer(object):
    @pytest.fixture(params=("diy", "gke"))
    def infra(self, request):
        yield request.param

    @pytest.fixture(params=({}, {'A_GLOBAL_DIGIT': '0.01', 'A_GLOBAL_STRING': 'test'},
                            {'A_GLOBAL_DIGIT': '0.01', 'A_GLOBAL_STRING': 'test',
                             'INFRASTRUCTURE': 'illegal', 'ARTIFACT_NAME': 'illegal'}))
    def global_env(self, request):
        yield request.param

    @pytest.fixture(params=(True, False))
    def admin_access(self, request):
        yield request.param

    @pytest.fixture(params=(
            (False, None),
            (True, 8080),
            (True, "8080"),
            (True, "http")
    ))
    def prometheus(self, request, has_ports):
        enabled, port = request.param
        if not has_ports:
            enabled = False
        yield PrometheusSpec(enabled, port, '/internal-backstage/prometheus')

    @pytest.fixture(params=(True, False))
    def has_ports(self, request):
        yield request.param

    @pytest.fixture(params=(True, False))
    def secrets_in_environment(self, request):
        yield request.param

    @pytest.fixture
    def deployer(self, infra, global_env):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.infrastructure = infra
        config.environment = "test"
        config.global_env = global_env
        config.secrets_init_container_image = None
        config.secrets_service_account_name = None
        return DeploymentDeployer(config)

    @pytest.fixture
    def secrets_init_container_deployer(self, infra, global_env):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.infrastructure = infra
        config.environment = "test"
        config.global_env = global_env
        config.secrets_init_container_image = "finntech/testimage:version"
        config.secrets_service_account_name = "secretsmanager"
        return DeploymentDeployer(config)

    @pytest.mark.parametrize("deployer_name", (
            "deployer",
            "secrets_init_container_deployer",
    ))
    def test_deploy_new_deployment(self, request, infra, global_env, post, deployer_name, app_spec, admin_access,
                                   prometheus, has_ports, secrets_in_environment):
        if has_ports:
            ports = app_spec.ports
            health_checks = app_spec.health_checks
        else:
            ports = []
            exec_check = CheckSpec(http=None, tcp=None, execute=ExecCheckSpec(command="/app/check.sh"),
                                   initial_delay_seconds=10, period_seconds=10, success_threshold=1,
                                   timeout_seconds=1)
            health_checks = HealthCheckSpec(liveness=exec_check, readiness=exec_check)

        app_spec = app_spec._replace(
            admin_access=admin_access,
            prometheus=prometheus,
            ports=ports,
            health_checks=health_checks,
            secrets_in_environment=secrets_in_environment
        )
        deployer = request.getfuncargvalue(deployer_name)
        deployer.deploy(app_spec, SELECTOR, LABELS)

        expected_volumes = _get_expected_volumes(app_spec, deployer)
        expected_init_volume_mounts, expected_volume_mounts = _get_expected_volume_mounts(app_spec, deployer)

        if deployer._uses_secrets_init_container():
            init_containers = [{
                'name': (INIT_CONTAINER_NAME),
                'image': 'finntech/testimage:version',
                'volumeMounts': expected_init_volume_mounts,
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
        else:
            init_containers = []

        service_account_name = "default"

        if deployer._uses_secrets_init_container():
            service_account_name = "secretsmanager"

        base_expected_health_check = {
            'initialDelaySeconds': 10,
            'periodSeconds': 10,
            'successThreshold': 1,
            'timeoutSeconds': 1,
        }
        if has_ports:
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
        if secrets_in_environment:
            expected_env_from.append({
                'secretRef': {
                    'name': app_spec.name,
                    'optional': True,
                }
            })

        expected_deployment = {
            'metadata': pytest.helpers.create_metadata(app_spec.name, labels=LABELS),
            'spec': {
                'selector': {'matchLabels': SELECTOR},
                'template': {
                    'spec': {
                        'dnsPolicy': 'ClusterFirst',
                        'automountServiceAccountToken': deployer._uses_secrets_init_container() or admin_access,
                        'serviceAccountName': service_account_name,
                        'restartPolicy': 'Always',
                        'volumes': expected_volumes,
                        'imagePullSecrets': [],
                        'containers': [{
                            'livenessProbe': expected_liveness_check,
                            'name': app_spec.name,
                            'image': 'finntech/testimage:version',
                            'volumeMounts': expected_volume_mounts,
                            'env': create_environment_variables(infra, global_env=global_env),
                            'envFrom': expected_env_from,
                            'imagePullPolicy': 'IfNotPresent',
                            'readinessProbe': expected_readiness_check,
                            'ports': [{'protocol': 'TCP', 'containerPort': 8080, 'name': 'http'}] if has_ports else [],
                            'resources': {}
                        }],
                        'initContainers': init_containers
                    },
                    'metadata': pytest.helpers.create_metadata(app_spec.name, prometheus=prometheus.enabled,
                                                               labels=_get_expected_template_labels())
                },
                'replicas': 3,
                'revisionHistoryLimit': 5
            }
        }
        pytest.helpers.assert_any_call(post, DEPLOYMENTS_URI, expected_deployment)

    def test_deploy_new_deployment_with_custom_labels_and_annotations(self, request, infra, global_env, post, app_spec,
                                                                      prometheus):
        labels = LabelAndAnnotationSpec(deployment={"custom": "label"}, horizontal_pod_autoscaler={}, ingress={}, service={})
        annotations = LabelAndAnnotationSpec(deployment={"custom": "annotation"}, horizontal_pod_autoscaler={}, ingress={}, service={})
        app_spec = app_spec._replace(prometheus=prometheus, labels=labels, annotations=annotations)
        deployer = request.getfuncargvalue("deployer")
        deployer.deploy(app_spec, SELECTOR, LABELS)

        expected_volumes = _get_expected_volumes(app_spec, deployer)
        expected_init_volume_mounts, expected_volume_mounts = _get_expected_volume_mounts(app_spec, deployer)

        expected_deployment = {
            'metadata': pytest.helpers.create_metadata(app_spec.name, labels={"deployment_deployer": "pass through",
                                                                              "custom": "label"},
                                                       annotations={"custom": "annotation"}),
            'spec': {
                'selector': {'matchLabels': SELECTOR},
                'template': {
                    'spec': {
                        'dnsPolicy': 'ClusterFirst',
                        'automountServiceAccountToken': False,
                        'serviceAccountName': "default",
                        'restartPolicy': 'Always',
                        'volumes': expected_volumes,
                        'imagePullSecrets': [],
                        'containers': [{
                            'livenessProbe': {
                                'initialDelaySeconds': 10,
                                'periodSeconds': 10,
                                'successThreshold': 1,
                                'timeoutSeconds': 1,
                                'tcpSocket': {
                                    'port': 8080
                                }
                            },
                            'name': app_spec.name,
                            'image': 'finntech/testimage:version',
                            'volumeMounts': expected_volume_mounts,
                            'env': create_environment_variables(infra, global_env=global_env),
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
                        }],
                        'initContainers': []
                    },
                    'metadata': pytest.helpers.create_metadata(app_spec.name, prometheus=prometheus.enabled,
                                                               labels=_get_expected_template_labels())
                },
                'replicas': 3,
                'revisionHistoryLimit': 5
            }
        }
        pytest.helpers.assert_any_call(post, DEPLOYMENTS_URI, expected_deployment)

    @pytest.mark.parametrize("previous_replicas,max_replicas,min_replicas,cpu_request,expected_replicas", (
            (5, 3, 2, None, 3),
            (5, 3, 2, "1", 5),
    ))
    def test_replicas_when_autoscaler_enabled(self, previous_replicas, max_replicas, min_replicas, cpu_request,
                                              expected_replicas, infra, global_env, deployer, app_spec, get, put, post):
        app_spec = app_spec._replace(
            replicas=max_replicas,
            autoscaler=AutoscalerSpec(enabled=True, min_replicas=min_replicas, cpu_threshold_percentage=50),
            image="finntech/testimage:version2")
        if cpu_request:
            app_spec = app_spec._replace(
                resources=ResourcesSpec(
                    requests=ResourceRequirementSpec(cpu=cpu_request, memory=None),
                    limits=ResourceRequirementSpec(cpu=None, memory=None)))
        expected_volumes = _get_expected_volumes(app_spec, deployer)
        expected_init_volume_mounts, expected_volume_mounts = _get_expected_volume_mounts(app_spec, deployer)

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
                        'restartPolicy': 'Always',
                        'volumes': expected_volumes,
                        'imagePullSecrets': [],
                        'containers': [{
                            'livenessProbe': {
                                'initialDelaySeconds': 10,
                                'periodSeconds': 10,
                                'successThreshold': 1,
                                'timeoutSeconds': 1,
                                'tcpSocket': {
                                    'port': 8080
                                }
                            },
                            'name': 'testapp',
                            'image': 'finntech/testimage:version',
                            'volumeMounts': expected_volume_mounts,
                            'env': create_environment_variables(infra, global_env=global_env),
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

        deployer.deploy(app_spec, SELECTOR, LABELS)
        expected_deployment = {
            'metadata': pytest.helpers.create_metadata('testapp', labels=LABELS),
            'spec': {
                'selector': {'matchLabels': SELECTOR},
                'template': {
                    'spec': {
                        'dnsPolicy': 'ClusterFirst',
                        'automountServiceAccountToken': False,
                        'serviceAccountName': 'default',
                        'restartPolicy': 'Always',
                        'volumes': expected_volumes,
                        'imagePullSecrets': [],
                        'containers': [{
                            'livenessProbe': {
                                'initialDelaySeconds': 10,
                                'periodSeconds': 10,
                                'successThreshold': 1,
                                'timeoutSeconds': 1,
                                'tcpSocket': {
                                    'port': 8080
                                }
                            },
                            'name': 'testapp',
                            'image': 'finntech/testimage:version2',
                            'volumeMounts': expected_volume_mounts,
                            'env': create_environment_variables(infra, global_env=global_env, version="version2"),
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
                                'timeoutSeconds': 1,
                                'httpGet': {
                                    'path': '/',
                                    'scheme': 'HTTP',
                                    'port': 8080,
                                    'httpHeaders': []
                                }
                            },
                            'ports': [{'protocol': 'TCP', 'containerPort': 8080, 'name': 'http'}],
                            'resources': {
                                'requests': {'cpu': cpu_request}
                            } if cpu_request else {}
                        }],
                        'initContainers': []
                    },
                    'metadata': pytest.helpers.create_metadata('testapp', prometheus=True, labels=_get_expected_template_labels())
                },
                'replicas': expected_replicas,
                'revisionHistoryLimit': 5
            }
        }
        pytest.helpers.assert_no_calls(post)
        pytest.helpers.assert_any_call(put, DEPLOYMENTS_URI + "testapp", expected_deployment)


def create_environment_variables(infrastructure, global_env=None, version="version"):
    environment = [{'name': 'ARTIFACT_NAME', 'value': 'testapp'},
                   {'name': 'LOG_STDOUT', 'value': 'true'},
                   {'name': 'VERSION', 'value': version},
                   {'name': 'CONSTRETTO_TAGS', 'value': 'kubernetes-test,kubernetes,test'},
                   {'name': 'FIAAS_INFRASTRUCTURE', 'value': infrastructure},
                   {'name': 'FIAAS_ENVIRONMENT', 'value': 'test'},
                   {'name': 'LOG_FORMAT', 'value': 'json'},
                   {'name': 'IMAGE', 'value': 'finntech/testimage:' + version},
                   {'name': 'FINN_ENV', 'value': 'test'}, ]
    if global_env:
        environment.append({'name': 'A_GLOBAL_STRING', 'value': global_env['A_GLOBAL_STRING']})
        environment.append({'name': 'FIAAS_A_GLOBAL_STRING', 'value': global_env['A_GLOBAL_STRING']})
        environment.append({'name': 'A_GLOBAL_DIGIT', 'value': global_env['A_GLOBAL_DIGIT']})
        environment.append({'name': 'FIAAS_A_GLOBAL_DIGIT', 'value': global_env['A_GLOBAL_DIGIT']})
    return environment


def _get_expected_template_labels():
    expected_template_labels = {"fiaas/status": "active"}
    expected_template_labels.update(LABELS)
    return expected_template_labels


def _get_expected_volumes(app_spec, deployer):
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
    if deployer._uses_secrets_init_container():
        expected_volumes = [init_secret_volume, init_config_map_volume, config_map_volume]
    else:
        expected_volumes = [secret_volume, config_map_volume]
    return expected_volumes


def _get_expected_volume_mounts(app_spec, deployer):
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
    expected_volume_mounts = [secret_volume_mount, config_map_volume_mount]
    if deployer._uses_secrets_init_container():
        expected_init_volume_mounts = [init_secret_volume_mount, init_config_map_volume_mount, config_map_volume_mount]
    else:
        expected_init_volume_mounts = []
    return expected_init_volume_mounts, expected_volume_mounts
