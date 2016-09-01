from fiaas_deploy_daemon.specs.models import AppSpec, ServiceSpec, ProbeSpec, ResourceRequirementSpec, ResourcesSpec, PrometheusSpec
from fiaas_deploy_daemon.deployer.kubernetes import K8s
from k8s.client import NotFound

import mock
import pytest
from util import assert_any_call_with_useful_error_message

SOME_RANDOM_IP = '192.0.2.0'
WHITELIST_IP_DETAILED = '192.0.0.1/32'
WHITELIST_IP_UNDETAILED = '192.0.0.1/24'
DEFAULT_SERVICE_WHITELIST_COPY = ['80.91.33.141/32', '80.91.33.151/32', '80.91.33.147/32']

SERVICES_URI = '/api/v1/namespaces/default/services/'
DEPLOYMENTS_URI = '/apis/extensions/v1beta1/namespaces/default/deployments/'
INGRESSES_URI = '/apis/extensions/v1beta1/namespaces/default/ingresses/'


def test_make_selector():
    name = 'app-name'
    app_spec = AppSpec(namespace=None, name=name, image=None, services=None, replicas=None, resources=None,
                       admin_access=None, has_secrets=None, prometheus=None)
    assert K8s._make_selector(app_spec) == {'app': name}


def test_resolve_finn_env_default():
    assert K8s._resolve_cluster_env("default_cluster") == "default_cluster"


def test_resolve_finn_env_cluster_match():
    assert K8s._resolve_cluster_env("prod1") == "prod"


class TestK8s(object):

    @pytest.fixture
    def k8s_diy(self):
        # Configuration.__init__ interrogates the environment and filesystem, and we don't care about that, so use a mock
        config = mock.Mock(return_value="")
        config.version = "1"
        config.target_cluster = "dev"
        config.infrastructure = "diy"
        return K8s(config)

    @pytest.fixture
    def k8s_gke(self):
        # Configuration.__init__ interrogates the environment and filesystem, and we don't care about that, so use a mock
        config = mock.Mock(return_value="")
        config.version = "1"
        config.target_cluster = "dev"
        config.infrastructure = "gke"
        return K8s(config)

    @pytest.fixture
    def app_spec(self):
        return AppSpec(admin_access=None,
                       name="testapp",
                       replicas=3,
                       image="finntech/testimage:version",
                       namespace="default",
                       services=[create_simple_http_service_spec()],
                       has_secrets=False,
                       resources=create_empty_resource_spec(),
                       prometheus=None)

    @pytest.fixture
    def app_spec_thrift_and_http(self):
        return AppSpec(
            admin_access=None,
            name="testapp",
            replicas=3,
            image="finntech/testimage:version",
            namespace="default",
            services=[
                create_simple_http_service_spec(),
                ServiceSpec(readiness=ProbeSpec(name="7999",
                                                type='thrift',
                                                path="/"),
                            exposed_port=7999,
                            probe_delay=60,
                            service_port=7999,
                            liveness=ProbeSpec(name="7999",
                                               type='thrift',
                                               path="/"),
                            type="thrift")
            ],
            has_secrets=False,
            resources=create_empty_resource_spec(),
            prometheus=None)

    def test_make_loadbalancer_source_ranges(self, app_spec_thrift_and_http):
        assert_lb_sourceranges_output(app_spec_thrift_and_http, [])
        app_spec_thrift_and_http.services[0].whitelist = "{}, {}".format(WHITELIST_IP_DETAILED, WHITELIST_IP_UNDETAILED)
        assert_lb_sourceranges_output(app_spec_thrift_and_http, [WHITELIST_IP_DETAILED, WHITELIST_IP_UNDETAILED])
        app_spec_thrift_and_http.services[0].whitelist = 'joke, output, we, copy'
        assert_lb_sourceranges_output(app_spec_thrift_and_http, ['joke', 'output', 'we', 'copy'])

    @mock.patch('k8s.client.Client.get')
    def test_deploy_to_invalid_infrastructure_should_fail(self, get):
        get.side_effect = NotFound()

        config = mock.Mock(return_value="")
        config.version = "1"
        config.target_cluster = "dev"
        config.infrastructure = "invalid"
        k8s = K8s(config)

        with pytest.raises(ValueError):
            k8s.deploy(mock.MagicMock())

    @mock.patch('k8s.client.Client.post')
    @mock.patch('k8s.client.Client.get')
    def test_deploy_new_ingress(self, get, post, k8s_diy, app_spec):
        get.side_effect = NotFound()

        k8s_diy.deploy(app_spec)

        expected_ingress = {
            'spec': {
                'rules': [{
                    'host': 'testapp.k8s.dev.finn.no',
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
        dev_k8s_ingress = {
            'spec': {
                'rules': [{
                    'host': 'testapp.dev-k8s.finntech.no',
                    'http': {
                        'paths': [{
                            'path': '/',
                            'backend': {
                                'serviceName': 'testapp',
                                'servicePort': 80
                            }}]
                    }
                }]
            },
            'metadata': create_metadata('testapp-dev-k8s.finntech.no', app_name='testapp')
        }

        assert_any_call_with_useful_error_message(post, INGRESSES_URI, expected_ingress)
        assert_any_call_with_useful_error_message(post, INGRESSES_URI, dev_k8s_ingress)

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
                    'name': 'http8080',
                    'port': 80
                }],
                'sessionAffinity': 'None'
            },
            'metadata': create_metadata('testapp')
        }

        assert_any_call_with_useful_error_message(post, SERVICES_URI, expected_service)

    @mock.patch('k8s.client.Client.post')
    @mock.patch('k8s.client.Client.get')
    def test_deploy_new_service_with_multiple_ports(self, get, post, k8s_diy, app_spec_thrift_and_http):
        get.side_effect = NotFound()
        k8s_diy.deploy(app_spec_thrift_and_http)

        expected_http_service = create_simple_http_service('testapp', 'ClusterIP')

        expected_thrift_service = {
            'spec': {
                'selector': {'app': 'testapp'},
                'type': 'NodePort',
                "loadBalancerSourceRanges": [],
                'ports': [
                    {
                        'protocol': 'TCP',
                        'targetPort': 7999,
                        'name': 'thrift7999-thrift',
                        'port': 7999,
                        'nodePort': 7999
                    },
                ],
                'sessionAffinity': 'None'
            },
            'metadata': create_metadata('testapp-thrift', app_name='testapp')
        }
        assert_any_call_with_useful_error_message(post, SERVICES_URI, expected_http_service)
        assert_any_call_with_useful_error_message(post, SERVICES_URI, expected_thrift_service)

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
                                'initialDelaySeconds': 60,
                                'httpGet': {
                                    'path': ProbeSpec(name='8080', type='http',
                                                      path='/internal-backstage/health/services'),
                                    'scheme': 'HTTP',
                                    'port': 8080}
                            },
                            'name': 'testapp',
                            'image': 'finntech/testimage:version',
                            'volumeMounts': [],
                            'env': create_environment_variables('diy'),
                            'imagePullPolicy': 'IfNotPresent',
                            'readinessProbe': {
                                'initialDelaySeconds': 60,
                                'httpGet': {
                                    'path': ProbeSpec(name='8080', type='http',
                                                      path='/internal-backstage/health/services'),
                                    'scheme': 'HTTP',
                                    'port': 8080
                                }
                            },
                            'ports': [{'protocol': 'TCP', 'containerPort': 8080, 'name': 'http8080'}],
                            'resources': {}
                        }]
                    },
                    'metadata': create_metadata('testapp', annotations=True)
                },
                'replicas': 3
            },
            'strategy': 'RollingUpdate'
        }
        assert_any_call_with_useful_error_message(post, DEPLOYMENTS_URI, expected_deployment)

    @mock.patch('k8s.client.Client.post')
    @mock.patch('k8s.client.Client.get')
    def test_deploy_new_deployment_without_prometheus_scraping(self, get, post, k8s_diy, app_spec):
        get.side_effect = NotFound()

        app_spec.prometheus = PrometheusSpec(False)
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
                                'initialDelaySeconds': 60,
                                'httpGet': {
                                    'path': ProbeSpec(name='8080', type='http',
                                                      path='/internal-backstage/health/services'),
                                    'scheme': 'HTTP',
                                    'port': 8080}
                            },
                            'name': 'testapp',
                            'image': 'finntech/testimage:version',
                            'volumeMounts': [],
                            'env': create_environment_variables('diy'),
                            'imagePullPolicy': 'IfNotPresent',
                            'readinessProbe': {
                                'initialDelaySeconds': 60,
                                'httpGet': {
                                    'path': ProbeSpec(name='8080', type='http',
                                                      path='/internal-backstage/health/services'),
                                    'scheme': 'HTTP',
                                    'port': 8080
                                }
                            },
                            'ports': [{'protocol': 'TCP', 'containerPort': 8080, 'name': 'http8080'}],
                            'resources': {}
                        }]
                    },
                    'metadata': create_metadata('testapp', annotations=False)
                },
                'replicas': 3
            },
            'strategy': 'RollingUpdate'
        }
        assert_any_call_with_useful_error_message(post, DEPLOYMENTS_URI, expected_deployment)

    @mock.patch('fiaas_deploy_daemon.deployer.gke.Gke.get_or_create_dns', mock.Mock())
    @mock.patch('fiaas_deploy_daemon.deployer.gke.Gke.get_or_create_static_ip')
    @mock.patch('k8s.client.Client.post')
    @mock.patch('k8s.client.Client.get')
    def test_deploy_new_service_to_gke(self, get, post, get_or_create_static_ip, k8s_gke, app_spec):
        get.side_effect = NotFound()
        get_or_create_static_ip.return_value = SOME_RANDOM_IP
        k8s_gke.deploy(app_spec)
        expected_service = create_simple_http_service(
            'testapp', 'LoadBalancer', lb_source_range=DEFAULT_SERVICE_WHITELIST_COPY, loadbalancer_ip=SOME_RANDOM_IP)

        assert_any_call_with_useful_error_message(post, SERVICES_URI, expected_service)

    @mock.patch('fiaas_deploy_daemon.deployer.gke.Gke.get_or_create_dns', mock.Mock())
    @mock.patch('fiaas_deploy_daemon.deployer.gke.Gke.get_or_create_static_ip')
    @mock.patch('k8s.client.Client.post')
    @mock.patch('k8s.client.Client.get')
    def test_deploy_new_service_with_multiple_ports_to_gke(self, get, post, get_or_create_static_ip,
                                                           k8s_gke, app_spec_thrift_and_http):
        get.side_effect = NotFound()
        get_or_create_static_ip.return_value = SOME_RANDOM_IP
        k8s_gke.deploy(app_spec_thrift_and_http)

        expected_service = {
            'spec': {
                'selector': {'app': 'testapp'},
                'loadBalancerIP': SOME_RANDOM_IP,
                'type': 'LoadBalancer',
                "loadBalancerSourceRanges": DEFAULT_SERVICE_WHITELIST_COPY,
                'ports': [
                    {
                        'protocol': 'TCP',
                        'targetPort': 8080,
                        'name': 'http8080',
                        'port': 80
                    },
                    {
                        'protocol': 'TCP',
                        'targetPort': 7999,
                        'name': 'thrift7999',
                        'port': 7999
                    }
                ],
                'sessionAffinity': 'None'
            },
            'metadata': create_metadata('testapp')
        }
        assert_any_call_with_useful_error_message(post, SERVICES_URI, expected_service)

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
                                'initialDelaySeconds': 60,
                                'httpGet': {
                                    'path': ProbeSpec(name='8080', type='http',
                                                      path='/internal-backstage/health/services'),
                                    'scheme': 'HTTP',
                                    'port': 8080}
                            },
                            'name': 'testapp',
                            'image': 'finntech/testimage:version',
                            'volumeMounts': [],
                            'env': create_environment_variables('gke'),
                            'imagePullPolicy': 'IfNotPresent',
                            'readinessProbe': {
                                'initialDelaySeconds': 60,
                                'httpGet': {
                                    'path': ProbeSpec(name='8080', type='http',
                                                      path='/internal-backstage/health/services'),
                                    'scheme': 'HTTP',
                                    'port': 8080
                                }
                            },
                            'ports': [{'protocol': 'TCP', 'containerPort': 8080, 'name': 'http8080'}],
                            'resources': {}
                        }]
                    },
                    'metadata': create_metadata('testapp', annotations=True)
                },
                'replicas': 3
            },
            'strategy': 'RollingUpdate'
        }
        assert_any_call_with_useful_error_message(post, DEPLOYMENTS_URI, expected_deployment)

    @mock.patch('fiaas_deploy_daemon.deployer.gke.Gke.get_or_create_dns', mock.Mock())
    @mock.patch('fiaas_deploy_daemon.deployer.gke.Gke.get_or_create_static_ip')
    @mock.patch('k8s.client.Client.post')
    @mock.patch('k8s.client.Client.get')
    def test_deploy_service_with_multiple_whitelist_ips_to_gke(self, get, post, get_or_create_static_ip, k8s_gke, app_spec_thrift_and_http):
        get.side_effect = NotFound()
        app_spec_thrift_and_http.services[0].whitelist = "{}, {}".format(WHITELIST_IP_DETAILED, WHITELIST_IP_UNDETAILED)
        get_or_create_static_ip.return_value = SOME_RANDOM_IP
        k8s_gke.deploy(app_spec_thrift_and_http)

        expected_service = {
            'spec': {
                'selector': {'app': 'testapp'},
                'loadBalancerIP': SOME_RANDOM_IP,
                'type': 'LoadBalancer',
                "loadBalancerSourceRanges":
                    [WHITELIST_IP_DETAILED, WHITELIST_IP_UNDETAILED] + DEFAULT_SERVICE_WHITELIST_COPY,
                'ports': [
                    {
                        'protocol': 'TCP',
                        'targetPort': 8080,
                        'name': 'http8080',
                        'port': 80
                    },
                    {
                        'protocol': 'TCP',
                        'targetPort': 7999,
                        'name': 'thrift7999',
                        'port': 7999
                    }
                ],
                'sessionAffinity': 'None'
            },
            'metadata': create_metadata('testapp')
        }
        assert_any_call_with_useful_error_message(post, SERVICES_URI, expected_service)

    @mock.patch('fiaas_deploy_daemon.deployer.gke.Gke.get_or_create_dns', mock.Mock())
    @mock.patch('fiaas_deploy_daemon.deployer.gke.Gke.get_or_create_static_ip')
    @mock.patch('k8s.client.Client.post')
    @mock.patch('k8s.client.Client.get')
    def test_deploy_service_with_whitelist_to_gke(self, get, post, get_or_create_static_ip, k8s_gke, app_spec):
        get.side_effect = NotFound()
        app_spec.services[0].whitelist = "{}, {}".format(WHITELIST_IP_DETAILED, WHITELIST_IP_UNDETAILED)
        get_or_create_static_ip.return_value = SOME_RANDOM_IP
        k8s_gke.deploy(app_spec)

        expected_service = create_simple_http_service(
            'testapp',
            'LoadBalancer',
            lb_source_range=[WHITELIST_IP_DETAILED, WHITELIST_IP_UNDETAILED] + DEFAULT_SERVICE_WHITELIST_COPY,
            loadbalancer_ip=SOME_RANDOM_IP)

        assert_any_call_with_useful_error_message(post, SERVICES_URI, expected_service)


def assert_lb_sourceranges_output(app_spec, expected_output_array):
    source_ranges_array = K8s._make_loadbalancer_source_ranges(app_spec)
    if len(expected_output_array) > 1:
        for expected_output in expected_output_array:
            assert expected_output in source_ranges_array
        assert len(source_ranges_array) is len(expected_output_array)
    else:
        assert source_ranges_array == expected_output_array


def create_simple_http_service_spec():
    return ServiceSpec(readiness=ProbeSpec(name="8080",
                                           type='http',
                                           path='/internal-backstage/health/services'),
                       ingress="/",
                       exposed_port=8080,
                       probe_delay=60,
                       service_port=80,
                       liveness=ProbeSpec(name="8080",
                                          type='http',
                                          path='/internal-backstage/health/services'),
                       type="http")


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


def create_metadata(resource_name, app_name=None, namespace='default', annotations=False):
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
            'prometheus.io/scrape': 'true'
        }
    return metadata


def create_environment_variables(infrastructure, appname='testapp'):
    return [
        {'name': 'ARTIFACT_NAME', 'value': appname},
        {'name': 'LOG_STDOUT', 'value': 'true'},
        {'name': 'CONSTRETTO_TAGS', 'value': 'kubernetes-dev,kubernetes,dev'},
        {'name': 'FIAAS_INFRASTRUCTURE', 'value': infrastructure},
        {'name': 'LOG_FORMAT', 'value': 'json'},
        {'name': 'FINN_ENV', 'value': 'dev'},
        {'name': 'IMAGE', 'value': 'finntech/testimage:version'},
        {'name': 'VERSION', 'value': 'version'}
    ]
