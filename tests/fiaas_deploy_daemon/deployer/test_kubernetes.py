from fiaas_deploy_daemon.specs.models import AppSpec, ServiceSpec, ProbeSpec, ResourceRequirementSpec, ResourcesSpec
from fiaas_deploy_daemon.deployer.kubernetes import K8s
from k8s.client import NotFound
import mock
import pytest


def test_make_selector():
    name = 'app-name'
    app_spec = AppSpec(namespace=None, name=name, image=None, services=None, replicas=None, resources=None,
                       admin_access=None, has_secrets=None)
    assert K8s._make_selector(app_spec) == {'app': name}


def test_resolve_finn_env_default():
    assert K8s._resolve_cluster_env("default_cluster") == "default_cluster"


def test_resolve_finn_env_cluster_match():
    assert K8s._resolve_cluster_env("prod1") == "prod1"


class TestK8s(object):
    @pytest.fixture
    def k8s(self):
        # Configuration.__init__ interrogates the environment and filesystem, and we don't care about that, so use a mock
        config = mock.Mock(return_value="")
        config.version = "1"
        config.target_cluster = "dev"
        return K8s(config)

    @pytest.fixture
    def app_spec(self):
        return AppSpec(admin_access=None,
                       name="testapp",
                       replicas=3,
                       image="finntech/testimage:version",
                       namespace="default",
                       services=[ServiceSpec(readiness=ProbeSpec(name="8080",
                                                                 type='http',
                                                                 path='/internal-backstage/health/services'),
                                             ingress="/",
                                             exposed_port=8080,
                                             probe_delay=60,
                                             service_port=80,
                                             liveness=ProbeSpec(name="8080",
                                                                type='http',
                                                                path='/internal-backstage/health/services'),
                                             type="http")],
                       has_secrets=False,
                       resources=ResourcesSpec(requests=ResourceRequirementSpec(cpu=None, memory=None),
                                               limits=ResourceRequirementSpec(cpu=None, memory=None)))

    @mock.patch('k8s.client.Client.post')
    @mock.patch('k8s.client.Client.get')
    def test_deploy_new_ingress(self, get, post, k8s, app_spec):
        get.side_effect = NotFound()

        k8s.deploy(app_spec)

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
            'metadata': {
                'labels': {
                    'fiaas/version': 'version',
                    'app': 'testapp',
                    'fiaas/deployed_by': '1'
                },
                'namespace': 'default',
                'name': 'testapp'
            }
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
            'metadata': {
                'labels': {
                    'fiaas/version': 'version',
                    'app': 'testapp',
                    'fiaas/deployed_by': '1'
                },
                'namespace': 'default',
                'name': 'testapp-dev-k8s.finntech.no'
            }
        }

        assert_any_call_with_useful_error_message(post, '/apis/extensions/v1beta1/namespaces/default/ingresses/',
                                                  expected_ingress)
        assert_any_call_with_useful_error_message(post, '/apis/extensions/v1beta1/namespaces/default/ingresses/',
                                                  dev_k8s_ingress)

    @mock.patch('k8s.client.Client.post')
    @mock.patch('k8s.client.Client.get')
    def test_deploy_new_service(self, get, post, k8s, app_spec):
        get.side_effect = NotFound()
        k8s.deploy(app_spec)

        expected_service = {
            'spec': {
                'selector': {'app': 'testapp'},
                'type': 'ClusterIP',
                'ports': [{
                    'protocol': 'TCP',
                    'targetPort': 8080,
                    'name': 'http8080',
                    'port': 80
                }],
                'sessionAffinity': 'None'
            },
            'metadata': {
                'labels': {
                    'fiaas/version': 'version',
                    'app': 'testapp',
                    'fiaas/deployed_by': '1'
                },
                'namespace': 'default',
                'name': 'testapp'
            }
        }

        assert_any_call_with_useful_error_message(post, '/api/v1/namespaces/default/services/', expected_service)

    @mock.patch('k8s.client.Client.post')
    @mock.patch('k8s.client.Client.get')
    def test_deploy_new_deployment(self, get, post, k8s, app_spec):
        get.side_effect = NotFound()
        k8s.deploy(app_spec)

        expected_deployment = {
            'metadata': {
                'labels': {'fiaas/version': 'version', 'app': 'testapp', 'fiaas/deployed_by': '1'},
                'namespace': 'default',
                'name': 'testapp'
            },
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
                            'env': [
                                {'name': 'ARTIFACT_NAME', 'value': 'testapp'},
                                {'name': 'LOG_STDOUT', 'value': 'true'},
                                {'name': 'CONSTRETTO_TAGS', 'value': 'kubernetes,dev,kubernetes-dev'},
                                {'name': 'LOG_FORMAT', 'value': 'json'},
                                {'name': 'FINN_ENV', 'value': 'dev'},
                                {'name': 'IMAGE', 'value': 'finntech/testimage:version'},
                                {'name': 'VERSION', 'value': 'version'}
                            ],
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
                    'metadata': {
                        'labels': {'fiaas/version': 'version', 'app': 'testapp', 'fiaas/deployed_by': '1'},
                        'namespace': 'default',
                        'name': 'testapp',
                        'annotations': {
                            'prometheus.io/port': '8080',
                            'prometheus.io/path': '/internal-backstage/prometheus',
                            'prometheus.io/scrape': 'true'
                        }
                    }
                },
                'replicas': 3
            },
            'strategy': 'RollingUpdate'
        }

        uri = '/apis/extensions/v1beta1/namespaces/default/deployments/'
        assert_any_call_with_useful_error_message(post, uri, expected_deployment)


def assert_any_call_with_useful_error_message(mockk, uri, *args):
    """
    If an AssertionError is raised in the assert, find any other calls on mock where the first parameter is uri and
    append those calls to the AssertionErrors message to more easily find the cause of the test failure.
    """

    def format_call(call):
        return 'call({}, {})'.format(call[0], call[1])

    try:
        mockk.assert_any_call(uri, *args)
    except AssertionError as ae:
        other_calls = [call[0] for call in mockk.call_args_list if call[0][0] == uri]
        if other_calls:
            extra_info = '\n\nURI {} got the following other calls:\n{}'.format(uri, '\n'.join(
                format_call(call) for call in other_calls))
        raise AssertionError(ae.message + extra_info)
