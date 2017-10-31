#!/usr/bin/env python
# -*- coding: utf-8
import mock
import pytest

from fiaas_deploy_daemon.config import Configuration, HostRewriteRule
from fiaas_deploy_daemon.deployer.kubernetes.ingress import IngressDeployer
from fiaas_deploy_daemon.specs.models import AppSpec, ResourceRequirementSpec, ResourcesSpec, PrometheusSpec, \
    PortSpec, CheckSpec, HttpCheckSpec, TcpCheckSpec, HealthCheckSpec, AutoscalerSpec, ExecCheckSpec, \
    LabelAndAnnotationSpec, IngressItemSpec, IngressPathMappingSpec


LABELS = {"ingress_deployer": "pass through"}
INGRESSES_URI = '/apis/extensions/v1beta1/namespaces/default/ingresses/'

def app_spec(**kwargs):
    default_app_spec = AppSpec(
        name="testapp",
        namespace="default",
        image="finntech/testimage:version",
        replicas=3,
        autoscaler=AutoscalerSpec(enabled=False, min_replicas=2, cpu_threshold_percentage=50),
        resources=ResourcesSpec(requests=ResourceRequirementSpec(cpu=None, memory=None),
                                    limits=ResourceRequirementSpec(cpu=None, memory=None)),
        admin_access=False,
        secrets_in_environment=False,
        prometheus=PrometheusSpec(enabled=True, port='http', path='/internal-backstage/prometheus'),
        ports=[
            PortSpec(protocol="http", name="http", port=80, target_port=8080),
        ],
        health_checks=HealthCheckSpec(
            liveness=CheckSpec(tcp=TcpCheckSpec(port=8080), http=None, execute=None, initial_delay_seconds=10,
                               period_seconds=10, success_threshold=1, timeout_seconds=1),
            readiness=CheckSpec(http=HttpCheckSpec(path="/", port=8080, http_headers={}), tcp=None, execute=None,
                                initial_delay_seconds=10, period_seconds=10, success_threshold=1,
                                timeout_seconds=1)),
        teams=[u'foo'],
        tags=[u'bar'],
        deployment_id="test_app_deployment_id",
        labels=LabelAndAnnotationSpec({}, {}, {}, {}),
        annotations=LabelAndAnnotationSpec({}, {}, {}, {}),
        ingresses=[IngressItemSpec(host=None, pathmappings=[IngressPathMappingSpec(path="/", port=80)])]
    )

    return default_app_spec._replace(**kwargs)


def ingress(rules=None, metadata=None, expose=False):
    default_rules = [
        {'host': "testapp.svc.test.example.com",
          'http': {'paths': [{
              'path': '/',
              'backend': {
                  'serviceName': 'testapp',
                  'servicePort': 80,
              }}]
          }
        },
        {'host': "testapp.127.0.0.1.xip.io",
         'http': {'paths': [{
             'path': '/',
             'backend': {
                 'serviceName': 'testapp',
                 'servicePort': 80,
             }}]
         }
        },
    ]
    default_metadata = pytest.helpers.create_metadata('testapp', labels=LABELS, external=expose)

    expected_ingress = {
        'spec': {
            'rules': rules if rules else default_rules,
            'tls': [],
        },
        'metadata': metadata if metadata else default_metadata,
    }
    return expected_ingress

TEST_DATA = (
    # (test_case_name, provided_app_spec, expected_ingress)
    ("only_default_hosts", app_spec(), ingress()),
    ("single_explicit_host",
     app_spec(ingresses=[IngressItemSpec(host="foo.example.com",
                                         pathmappings=[IngressPathMappingSpec(path="/", port=80)])]),
     ingress(expose=True, rules=[
         {'host': "foo.example.com",
          'http': {'paths': [{
              'path': '/',
              'backend': {
                  'serviceName': 'testapp',
                  'servicePort': 80,
              }}]
          }
         },
         {'host': "testapp.svc.test.example.com",
          'http': {'paths': [{
              'path': '/',
              'backend': {
                  'serviceName': 'testapp',
                  'servicePort': 80,
              }}]
          }
        },
        {'host': "testapp.127.0.0.1.xip.io",
         'http': {'paths': [{
             'path': '/',
             'backend': {
                 'serviceName': 'testapp',
                 'servicePort': 80,
             }}]
         }
        }])
    ),
    ("single_explicit_host_multiple_paths",
     app_spec(ingresses=[IngressItemSpec(host="foo.example.com",
                                         pathmappings=[IngressPathMappingSpec(path="/", port=80),
                                                       IngressPathMappingSpec(path="/other", port=5000)])],
              ports=[
                  PortSpec(protocol="http", name="http", port=80, target_port=8080),
                  PortSpec(protocol="http", name="other", port=5000, target_port=8081),
              ]),
     ingress(expose=True, rules=[
         {'host': "foo.example.com",
          'http': {'paths': [{
              'path': '/',
              'backend': {
                  'serviceName': 'testapp',
                  'servicePort': 80,
              }},{
              'path': '/other',
              'backend': {
                  'serviceName': 'testapp',
                  'servicePort': 5000,
              }}]
          }
         },
         {'host': "testapp.svc.test.example.com",
          'http': {'paths': [{
              'path': '/',
              'backend': {
                  'serviceName': 'testapp',
                  'servicePort': 80,
              }},{
              'path': '/other',
              'backend': {
                  'serviceName': 'testapp',
                  'servicePort': 5000,
              }}]
          }
        },
        {'host': "testapp.127.0.0.1.xip.io",
         'http': {'paths': [{
             'path': '/',
             'backend': {
                 'serviceName': 'testapp',
                 'servicePort': 80,
             }},{
             'path': '/other',
             'backend': {
                 'serviceName': 'testapp',
                 'servicePort': 5000,
             }}]
         }
        }])
    ),
    ("multiple_explicit_hosts",
     app_spec(ingresses=[IngressItemSpec(host="foo.example.com",
                                         pathmappings=[IngressPathMappingSpec(path="/", port=80)]),
                         IngressItemSpec(host="bar.example.com",
                                         pathmappings=[IngressPathMappingSpec(path="/", port=80)])]),
     ingress(expose=True, rules=[
         {'host': "foo.example.com",
          'http': {'paths': [{
              'path': '/',
              'backend': {
                  'serviceName': 'testapp',
                  'servicePort': 80,
              }}]
          }
         },
         {'host': "bar.example.com",
          'http': {'paths': [{
              'path': '/',
              'backend': {
                  'serviceName': 'testapp',
                  'servicePort': 80,
              }}]
          }
         },
         {'host': "testapp.svc.test.example.com",
          'http': {'paths': [{
              'path': '/',
              'backend': {
                  'serviceName': 'testapp',
                  'servicePort': 80,
              }}]
          }
        },
        {'host': "testapp.127.0.0.1.xip.io",
         'http': {'paths': [{
             'path': '/',
             'backend': {
                 'serviceName': 'testapp',
                 'servicePort': 80,
             }}]
         }
        }])
    ),
    ("multiple_explicit_hosts_multiple_paths",
     app_spec(ingresses=[IngressItemSpec(host="foo.example.com",
                                         pathmappings=[IngressPathMappingSpec(path="/one", port=80),
                                                       IngressPathMappingSpec(path="/two", port=5000)]),
                         IngressItemSpec(host="bar.example.com",
                                         pathmappings=[IngressPathMappingSpec(path="/three", port=80),
                                                       IngressPathMappingSpec(path="/four", port=5000)])],
              ports=[
                  PortSpec(protocol="http", name="http", port=80, target_port=8080),
                  PortSpec(protocol="http", name="other", port=5000, target_port=8081),
              ]),
     ingress(expose=True, rules=[
         {'host': "foo.example.com",
          'http': {'paths': [{
              'path': '/one',
              'backend': {
                  'serviceName': 'testapp',
                  'servicePort': 80,
              }},{
              'path': '/two',
              'backend': {
                  'serviceName': 'testapp',
                  'servicePort': 5000,
              }}]
          }
         },
         {'host': "bar.example.com",
          'http': {'paths': [{
              'path': '/three',
              'backend': {
                  'serviceName': 'testapp',
                  'servicePort': 80,
              }},{
              'path': '/four',
              'backend': {
                  'serviceName': 'testapp',
                  'servicePort': 5000,
              }}]
          }
         },
         {'host': "testapp.svc.test.example.com",
          'http': {'paths': [{
              'path': '/one',
              'backend': {
                  'serviceName': 'testapp',
                  'servicePort': 80,
              }},{
              'path': '/two',
              'backend': {
                  'serviceName': 'testapp',
                  'servicePort': 5000,
              }},{
              'path': '/three',
              'backend': {
                  'serviceName': 'testapp',
                  'servicePort': 80,
              }},{
              'path': '/four',
              'backend': {
                  'serviceName': 'testapp',
                  'servicePort': 5000,
              }}]
          }
        },
        {'host': "testapp.127.0.0.1.xip.io",
         'http': {'paths': [{
              'path': '/one',
              'backend': {
                  'serviceName': 'testapp',
                  'servicePort': 80,
              }},{
              'path': '/two',
              'backend': {
                  'serviceName': 'testapp',
                  'servicePort': 5000,
              }},{
              'path': '/three',
              'backend': {
                  'serviceName': 'testapp',
                  'servicePort': 80,
              }},{
              'path': '/four',
              'backend': {
                  'serviceName': 'testapp',
                  'servicePort': 5000,
              }}]
         }
        }])),
    ("rewrite_host_simple",
     app_spec(ingresses=[IngressItemSpec(host="rewrite.example.com",
                                         pathmappings=[IngressPathMappingSpec(path="/", port=80)])]),
     ingress(expose=True, rules=[
         {'host': "test.rewrite.example.com",
          'http': {'paths': [{
              'path': '/',
              'backend': {
                  'serviceName': 'testapp',
                  'servicePort': 80,
              }}]
          }
         },
         {'host': "testapp.svc.test.example.com",
          'http': {'paths': [{
              'path': '/',
              'backend': {
                  'serviceName': 'testapp',
                  'servicePort': 80,
              }}]
          }
        },
        {'host': "testapp.127.0.0.1.xip.io",
         'http': {'paths': [{
             'path': '/',
             'backend': {
                 'serviceName': 'testapp',
                 'servicePort': 80,
             }}]
         }
        }])
    ),
    ("rewrite_host_regex_substitution",
     app_spec(ingresses=[IngressItemSpec(host="foo.rewrite.example.com",
                                         pathmappings=[IngressPathMappingSpec(path="/", port=80)])]),
     ingress(expose=True, rules=[
         {'host': "test.foo.rewrite.example.com",
          'http': {'paths': [{
              'path': '/',
              'backend': {
                  'serviceName': 'testapp',
                  'servicePort': 80,
              }}]
          }
         },
         {'host': "testapp.svc.test.example.com",
          'http': {'paths': [{
              'path': '/',
              'backend': {
                  'serviceName': 'testapp',
                  'servicePort': 80,
              }}]
          }
        },
        {'host': "testapp.127.0.0.1.xip.io",
         'http': {'paths': [{
             'path': '/',
             'backend': {
                 'serviceName': 'testapp',
                 'servicePort': 80,
             }}]
         }
        }])
    ),
    ("custom_labels_and_annotations",
     app_spec(labels=LabelAndAnnotationSpec(deployment={}, horizontal_pod_autoscaler={},
                                            ingress={"ingress_deployer": "pass through", "custom": "label"},
                                            service={}),
              annotations=LabelAndAnnotationSpec(deployment={}, horizontal_pod_autoscaler={},
                                                 ingress={"custom": "annotation"}, service={})),
     ingress(metadata=pytest.helpers.create_metadata('testapp', external=False,
                                                     labels={"ingress_deployer": "pass through", "custom": "label"},
                                                     annotations={"fiaas/expose": "false", "custom": "annotation"}))
    ),
)


class TestIngressDeployer(object):
    @pytest.fixture
    def deployer(self):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.ingress_suffixes = ["svc.test.example.com", "127.0.0.1.xip.io"]
        config.host_rewrite_rules = [
            HostRewriteRule("rewrite.example.com=test.rewrite.example.com"),
            HostRewriteRule(r"([a-z0-9](?:[-a-z0-9]*[a-z0-9])?).rewrite.example.com=test.\1.rewrite.example.com")]
        return IngressDeployer(config)


    def pytest_generate_tests(self, metafunc):
        fixtures = ("app_spec", "expected_ingress")
        if metafunc.cls == self.__class__ and all(fixname in metafunc.fixturenames for fixname in fixtures):
            for test_id, app_spec, expected_ingress in TEST_DATA:
                params = {"app_spec": app_spec, "expected_ingress": expected_ingress}
                metafunc.addcall(params, test_id)

    def test_ingress_deploy(self, post, deployer, app_spec, expected_ingress):
        deployer.deploy(app_spec, LABELS)

        pytest.helpers.assert_any_call(post, INGRESSES_URI, expected_ingress)

    @pytest.mark.parametrize("spec_name", (
        "app_spec_thrift_with_host",
        "app_spec_thrift",
        "app_spec_no_ports",
    ))
    def test_remove_existing_ingress_if_not_needed(self, request, delete, post, deployer, spec_name):
        app_spec = request.getfuncargvalue(spec_name)

        deployer.deploy(app_spec, LABELS)

        pytest.helpers.assert_no_calls(post, INGRESSES_URI)
        pytest.helpers.assert_any_call(delete, INGRESSES_URI + "testapp")


    def test_deploy_new_ingress_with_custom_labels_and_annotations(self, app_spec, post, deployer):
        expected_labels = {"ingress_deployer": "pass through", "custom": "label"}
        expected_annotations = {"fiaas/expose": "false", "custom": "annotation"}

        labels = LabelAndAnnotationSpec(deployment={}, horizontal_pod_autoscaler={}, ingress=expected_labels, service={})
        annotations = LabelAndAnnotationSpec(deployment={}, horizontal_pod_autoscaler={}, ingress=expected_annotations, service={})
        deployer.deploy(app_spec._replace(labels=labels, annotations=annotations), LABELS)
