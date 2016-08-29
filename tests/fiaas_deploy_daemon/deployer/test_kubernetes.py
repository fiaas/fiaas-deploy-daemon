import mock
import pytest
from fiaas_deploy_daemon.deployer.kubernetes import K8s
from fiaas_deploy_daemon.specs.models import AppSpec, ResourceRequirementSpec, ResourcesSpec, PrometheusSpec, \
    PortSpec, CheckSpec, HttpCheckSpec, TcpCheckSpec, HealthCheckSpec
from k8s.client import NotFound

SOME_RANDOM_IP = '192.0.2.0'
WHITELIST_IP_DETAILED = '192.0.0.1/32'
WHITELIST_IP_UNDETAILED = '192.0.0.1/24'
DEFAULT_SERVICE_WHITELIST_COPY = ['80.91.33.141/32', '80.91.33.151/32', '80.91.33.147/32']

SERVICES_URI = '/api/v1/namespaces/default/services/'
DEPLOYMENTS_URI = '/apis/extensions/v1beta1/namespaces/default/deployments/'
INGRESSES_URI = '/apis/extensions/v1beta1/namespaces/default/ingresses/'


def test_make_selector():
    name = 'app-name'
    app_spec = AppSpec(namespace=None, name=name, image=None, replicas=None, host=None, resources=None,
                       admin_access=None, has_secrets=None, prometheus=None, ports=None, health_checks=None)
    assert K8s._make_selector(app_spec) == {'app': name}


def test_resolve_finn_env_default():
    assert K8s._resolve_cluster_env("default_cluster") == "default_cluster"


def test_resolve_finn_env_cluster_match():
    assert K8s._resolve_cluster_env("prod1") == "prod"


def test_make_http_probe():
    check_spec = CheckSpec(http=HttpCheckSpec(path="/", port=8080,
                                              http_headers={"Authorization": "ZmlubjpqdXN0aW5iaWViZXJfeG94bw=="}),
                           tcp=None, execute=None, initial_delay_seconds=30, period_seconds=60, success_threshold=3,
                           timeout_seconds=10)
    probe = K8s._make_probe(check_spec)
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
    probe = K8s._make_probe(check_spec)
    assert probe.tcpSocket.port == 31337
    assert probe.initialDelaySeconds == 30
    assert probe.periodSeconds == 60
    assert probe.successThreshold == 3
    assert probe.timeoutSeconds == 10


def test_make_probe_should_fail_when_no_healthcheck_is_defined():
    check_spec = CheckSpec(tcp=None, execute=None, http=None, initial_delay_seconds=30, period_seconds=60,
                           success_threshold=3, timeout_seconds=10)
    with pytest.raises(RuntimeError):
        K8s._make_probe(check_spec)


class TestK8s(object):
    @pytest.fixture
    def k8s_diy(self):
        # Configuration.__init__ interrogates the environment and filesystem, and we don't care about that, so use a mock
        config = mock.Mock(return_value="")
        config.version = "1"
        config.target_cluster = "test"
        config.infrastructure = "diy"
        return K8s(config)

    @pytest.fixture
    def k8s_gke(self):
        # Configuration.__init__ interrogates the environment and filesystem, and we don't care about that, so use a mock
        config = mock.Mock(return_value="")
        config.version = "1"
        config.target_cluster = "test"
        config.infrastructure = "gke"
        return K8s(config)

    @pytest.fixture
    def app_spec(self):
        return AppSpec(
            name="testapp",
            namespace="default",
            image="finntech/testimage:version",
            replicas=3,
            host=None,
            resources=create_empty_resource_spec(),
            admin_access=None,
            has_secrets=False,
            prometheus=PrometheusSpec(enabled=True, port=8080, path='/internal-backstage/prometheus'),
            ports=[
                PortSpec(protocol="http", name="http", port=80, target_port=8080, path="/"),
            ],
            health_checks=HealthCheckSpec(
                liveness=CheckSpec(tcp=TcpCheckSpec(port=8080), http=None, execute=None, initial_delay_seconds=10,
                                   period_seconds=10, success_threshold=1, timeout_seconds=1),
                readiness=CheckSpec(http=HttpCheckSpec(path="/", port=8080, http_headers={}), tcp=None, execute=None,
                                    initial_delay_seconds=10, period_seconds=10, success_threshold=1,
                                    timeout_seconds=1)
            )
        )

    @pytest.fixture
    def app_spec_with_host(self):
        return AppSpec(
            name="testapp",
            namespace="default",
            image="finntech/testimage:version",
            replicas=3,
            host="www.finn.no",
            resources=create_empty_resource_spec(),
            admin_access=None,
            has_secrets=False,
            prometheus=PrometheusSpec(enabled=True, port=8080, path='/internal-backstage/prometheus'),
            ports=[
                PortSpec(protocol="http", name="http", port=80, target_port=8080, path="/"),
            ],
            health_checks=HealthCheckSpec(
                liveness=CheckSpec(tcp=TcpCheckSpec(port=8080), http=None, execute=None, initial_delay_seconds=10,
                                   period_seconds=10, success_threshold=1, timeout_seconds=1),
                readiness=CheckSpec(http=HttpCheckSpec(path="/", port=8080, http_headers={}), tcp=None, execute=None,
                                    initial_delay_seconds=10, period_seconds=10, success_threshold=1,
                                    timeout_seconds=1)
            )
        )

    @pytest.fixture
    def app_spec_thrift_and_http(self):
        return AppSpec(
            admin_access=None,
            name="testapp",
            replicas=3,
            image="finntech/testimage:version",
            namespace="default",
            has_secrets=False,
            host=None,
            resources=create_empty_resource_spec(),
            prometheus=PrometheusSpec(enabled=True, port=8080, path='/internal-backstage/prometheus'),
            ports=[
                PortSpec(protocol="http", name="http", port=80, target_port=8080, path="/"),
                PortSpec(protocol="tcp", name="thrift", port=7999, target_port=7999, path=None),
            ],
            health_checks=HealthCheckSpec(
                liveness=CheckSpec(tcp=TcpCheckSpec(port=7999), http=None, execute=None, initial_delay_seconds=10,
                                   period_seconds=10, success_threshold=1, timeout_seconds=1),
                readiness=CheckSpec(http=HttpCheckSpec(path="/", port=8080, http_headers={}), tcp=None, execute=None,
                                    initial_delay_seconds=10, period_seconds=10, success_threshold=1,
                                    timeout_seconds=1)
            ))

    @mock.patch('k8s.client.Client.post')
    @mock.patch('k8s.client.Client.get')
    def test_deploy_new_ingress(self, get, post, k8s_diy, app_spec_with_host):
        get.side_effect = NotFound()

        k8s_diy.deploy(app_spec_with_host)

        expected_ingress = {
            'spec': {
                'rules': [{
                    'host': 'test.finn.no',
                    'http': {'paths': [{
                        'path': '/',
                        'backend': {
                            'serviceName': 'testapp',
                            'servicePort': 80
                        }}]
                    }
                }]
            },
            'metadata': create_metadata('testapp')
        }

        pytest.helpers.assert_any_call_with_useful_error_message(post, INGRESSES_URI, expected_ingress)

    @mock.patch('k8s.client.Client.post')
    @mock.patch('k8s.client.Client.get')
    def test_no_host_no_ingress(self, get, post, k8s_diy, app_spec):
        get.side_effect = NotFound()

        k8s_diy.deploy(app_spec)

        pytest.helpers.assert_no_calls(post)

    @pytest.mark.parametrize("host,expected", [
        ("www.finn.no", "test.finn.no"),
        ("m.finn.no", "test.m.finn.no"),
        ("kart.finn.no", "test.kart.finn.no")
    ])
    def test_make_ingress_host(self, k8s_diy, host, expected):
        assert k8s_diy._make_ingress_host(host) == expected

    @mock.patch('k8s.client.Client.post')
    @mock.patch('k8s.client.Client.get')
    def test_deploy_new_service(self, get, post, k8s_diy, app_spec):
        get.side_effect = NotFound()
        k8s_diy.deploy(app_spec)

        expected_service = {
            'spec': {
                'selector': {'app': 'testapp'},
                'type': 'ClusterIP',
                "loadBalancerSourceRanges": [
                ],
                'ports': [{
                    'protocol': 'TCP',
                    'targetPort': 8080,
                    'name': 'http',
                    'port': 80
                }],
                'sessionAffinity': 'None'
            },
            'metadata': create_metadata('testapp')
        }

        pytest.helpers.assert_any_call_with_useful_error_message(post, SERVICES_URI, expected_service)

    @mock.patch('k8s.client.Client.post')
    @mock.patch('k8s.client.Client.get')
    def test_deploy_new_service_with_multiple_ports(self, get, post, k8s_diy, app_spec_thrift_and_http):
        get.side_effect = NotFound()
        k8s_diy.deploy(app_spec_thrift_and_http)

        expected_service = {
            'spec': {
                'selector': {'app': 'testapp'},
                'type': 'ClusterIP',
                "loadBalancerSourceRanges": [],
                'ports': [
                    {
                        'protocol': 'TCP',
                        'targetPort': 8080,
                        'name': 'http',
                        'port': 80
                    },
                    {
                        'protocol': 'TCP',
                        'targetPort': 7999,
                        'name': 'thrift',
                        'port': 7999
                    },
                ],
                'sessionAffinity': 'None'
            },
            'metadata': create_metadata('testapp')
        }
        pytest.helpers.assert_any_call_with_useful_error_message(post, SERVICES_URI, expected_service)

    @mock.patch('k8s.client.Client.post')
    @mock.patch('k8s.client.Client.get')
    def test_deploy_new_deployment(self, get, post, k8s_diy, app_spec):
        get.side_effect = NotFound()
        k8s_diy.deploy(app_spec)

        expected_deployment = {
            'metadata': create_metadata('testapp'),
            'spec': {
                'selector': {'matchLabels': {'app': 'testapp'}},
                'template': {
                    'spec': {
                        'dnsPolicy': 'ClusterFirst',
                        'serviceAccountName': 'fiaas-no-access',
                        'restartPolicy': 'Always',
                        'volumes': [],
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
                            'volumeMounts': [],
                            'env': create_environment_variables('diy'),
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
                    'metadata': create_metadata('testapp', annotations=True)
                },
                'replicas': 3
            },
            'strategy': 'RollingUpdate'
        }
        pytest.helpers.assert_any_call_with_useful_error_message(post, DEPLOYMENTS_URI, expected_deployment)

    @mock.patch('k8s.client.Client.post')
    @mock.patch('k8s.client.Client.get')
    def test_deploy_new_deployment_without_prometheus_scraping(self, get, post, k8s_diy, app_spec):
        get.side_effect = NotFound()

        app_spec = app_spec._replace(prometheus=PrometheusSpec(False, None, None))
        k8s_diy.deploy(app_spec)

        expected_deployment = {
            'metadata': create_metadata('testapp'),
            'spec': {
                'selector': {'matchLabels': {'app': 'testapp'}},
                'template': {
                    'spec': {
                        'dnsPolicy': 'ClusterFirst',
                        'serviceAccountName': 'fiaas-no-access',
                        'restartPolicy': 'Always',
                        'volumes': [],
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
                            'volumeMounts': [],
                            'env': create_environment_variables('diy'),
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
                    'metadata': create_metadata('testapp', annotations=False)
                },
                'replicas': 3
            },
            'strategy': 'RollingUpdate'
        }
        pytest.helpers.assert_any_call_with_useful_error_message(post, DEPLOYMENTS_URI, expected_deployment)

    @mock.patch('fiaas_deploy_daemon.deployer.gke.Gke.get_or_create_dns', mock.Mock())
    @mock.patch('fiaas_deploy_daemon.deployer.gke.Gke.get_or_create_static_ip')
    @mock.patch('k8s.client.Client.post')
    @mock.patch('k8s.client.Client.get')
    def test_deploy_new_deployment_to_gke(self, get, post, get_or_create_static_ip, k8s_gke, app_spec):
        get.side_effect = NotFound()
        get_or_create_static_ip.return_value = SOME_RANDOM_IP
        k8s_gke.deploy(app_spec)

        expected_deployment = {
            'metadata': create_metadata('testapp'),
            'spec': {
                'selector': {'matchLabels': {'app': 'testapp'}},
                'template': {
                    'spec': {
                        'dnsPolicy': 'ClusterFirst',
                        'serviceAccountName': 'fiaas-no-access',
                        'restartPolicy': 'Always',
                        'volumes': [],
                        'imagePullSecrets': [],
                        'containers': [{
                            'livenessProbe': {
                                'successThreshold': 1,
                                'initialDelaySeconds': 10,
                                'tcpSocket': {'port': 8080},
                                'timeoutSeconds': 1,
                                'periodSeconds': 10
                            },
                            'name': 'testapp',
                            'image': 'finntech/testimage:version',
                            'volumeMounts': [],
                            'env': create_environment_variables('gke'),
                            'imagePullPolicy': 'IfNotPresent',
                            'readinessProbe': {
                                'initialDelaySeconds': 10,
                                'httpGet': {
                                    'path': '/',
                                    'scheme': 'HTTP',
                                    'port': 8080,
                                    'httpHeaders': [],
                                },
                                'periodSeconds': 10,
                                'successThreshold': 1,
                                'timeoutSeconds': 1
                            },
                            'ports': [{'protocol': 'TCP', 'containerPort': 8080, 'name': 'http'}],
                            'resources': {}
                        }]
                    },
                    'metadata': create_metadata('testapp', annotations=True)
                },
                'replicas': 3
            },
            'strategy': 'RollingUpdate'
        }
        pytest.helpers.assert_any_call_with_useful_error_message(post, DEPLOYMENTS_URI, expected_deployment)


def create_empty_resource_spec():
    return ResourcesSpec(requests=ResourceRequirementSpec(cpu=None, memory=None),
                         limits=ResourceRequirementSpec(cpu=None, memory=None))


def create_simple_http_service(app_name, type, lb_source_range=[], loadbalancer_ip=None):
    simple_http_service = {
        'spec': {
            'selector': {'app': app_name},
            'type': type,
            "loadBalancerSourceRanges": lb_source_range,
            'ports': [
                {
                    'protocol': 'TCP',
                    'targetPort': 8080,
                    'name': 'http8080',
                    'port': 80
                }
            ],
            'sessionAffinity': 'None'
        },
        'metadata': create_metadata(app_name)
    }
    if loadbalancer_ip is not None:
        simple_http_service['spec']['loadBalancerIP'] = loadbalancer_ip
    return simple_http_service


def create_metadata(resource_name, app_name=None, namespace='default', annotations=False, prometheus='true'):
    metadata = {
        'labels': {
            'fiaas/version': 'version',
            'app': app_name if app_name else resource_name,
            'fiaas/deployed_by': '1'
        },
        'namespace': namespace,
        'name': resource_name
    }
    if annotations:
        metadata['annotations'] = {
            'prometheus.io/port': '8080',
            'prometheus.io/path': '/internal-backstage/prometheus',
            'prometheus.io/scrape': prometheus
        }
    return metadata


def create_environment_variables(infrastructure, appname='testapp'):
    return [
        {'name': 'ARTIFACT_NAME', 'value': appname},
        {'name': 'LOG_STDOUT', 'value': 'true'},
        {'name': 'CONSTRETTO_TAGS', 'value': 'kubernetes-test,kubernetes,test'},
        {'name': 'FIAAS_INFRASTRUCTURE', 'value': infrastructure},
        {'name': 'LOG_FORMAT', 'value': 'json'},
        {'name': 'FINN_ENV', 'value': 'test'},
        {'name': 'IMAGE', 'value': 'finntech/testimage:version'},
        {'name': 'VERSION', 'value': 'version'}
    ]
