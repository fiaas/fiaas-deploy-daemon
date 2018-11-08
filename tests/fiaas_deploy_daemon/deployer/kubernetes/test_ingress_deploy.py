#!/usr/bin/env python
# -*- coding: utf-8
import mock
import pytest
from k8s.models.common import ObjectMeta
from k8s.models.ingress import Ingress, IngressSpec, IngressTLS
from mock import create_autospec
from requests import Response

from fiaas_deploy_daemon.config import Configuration, HostRewriteRule
from fiaas_deploy_daemon.deployer.kubernetes.ingress import IngressDeployer, IngressTls
from fiaas_deploy_daemon.specs.models import AppSpec, ResourceRequirementSpec, ResourcesSpec, PrometheusSpec, \
    PortSpec, CheckSpec, HttpCheckSpec, TcpCheckSpec, HealthCheckSpec, AutoscalerSpec, \
    LabelAndAnnotationSpec, IngressItemSpec, IngressPathMappingSpec, StrongboxSpec, IngressTlsSpec

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
        datadog=False,
        ports=[
            PortSpec(protocol="http", name="http", port=80, target_port=8080),
        ],
        health_checks=HealthCheckSpec(
            liveness=CheckSpec(tcp=TcpCheckSpec(port=8080), http=None, execute=None, initial_delay_seconds=10,
                               period_seconds=10, success_threshold=1, failure_threshold=3, timeout_seconds=1),
            readiness=CheckSpec(http=HttpCheckSpec(path="/", port=8080, http_headers={}), tcp=None, execute=None,
                                initial_delay_seconds=10, period_seconds=10, success_threshold=1,
                                failure_threshold=3, timeout_seconds=1)),
        teams=[u'foo'],
        tags=[u'bar'],
        deployment_id="test_app_deployment_id",
        labels=LabelAndAnnotationSpec({}, {}, {}, {}, {}),
        annotations=LabelAndAnnotationSpec({}, {}, {}, {}, {}),
        ingresses=[IngressItemSpec(host=None, pathmappings=[IngressPathMappingSpec(path="/", port=80)])],
        strongbox=StrongboxSpec(enabled=False, iam_role=None, aws_region="eu-west-1", groups=None),
        singleton=False,
        ingress_tls=IngressTlsSpec(enabled=False, certificate_issuer=None)
    )

    return default_app_spec._replace(**kwargs)


def ingress(rules=None, metadata=None, expose=False, tls=None):
    default_rules = [{
        'host': "testapp.svc.test.example.com",
        'http': {
            'paths': [{
                'path': '/',
                'backend': {
                    'serviceName': 'testapp',
                    'servicePort': 80,
                }
            }]
        }
    }, {
        'host': "testapp.127.0.0.1.xip.io",
        'http': {
            'paths': [{
                'path': '/',
                'backend': {
                    'serviceName': 'testapp',
                    'servicePort': 80,
                }
            }]
        }
    }]
    default_metadata = pytest.helpers.create_metadata('testapp', labels=LABELS, external=expose)

    expected_ingress = {
        'spec': {
            'rules': rules if rules else default_rules,
            'tls': tls if tls else []
        },
        'metadata': metadata if metadata else default_metadata,
    }
    return expected_ingress


TEST_DATA = (
    # (test_case_name, provided_app_spec, expected_ingress)
    ("only_default_hosts", app_spec(), ingress()),
    ("single_explicit_host",
     app_spec(ingresses=[
         IngressItemSpec(host="foo.example.com", pathmappings=[IngressPathMappingSpec(path="/", port=80)])]),
     ingress(expose=True, rules=[{
         'host': "foo.example.com",
         'http': {
             'paths': [{
                 'path': '/',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 80,
                 }
             }]
         }
     }, {
         'host': "testapp.svc.test.example.com",
         'http': {
             'paths': [{
                 'path': '/',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 80,
                 }
             }]
         }
     }, {
         'host': "testapp.127.0.0.1.xip.io",
         'http': {
             'paths': [{
                 'path': '/',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 80,
                 }
             }]
         }
     }])),
    ("single_explicit_host_multiple_paths",
     app_spec(ingresses=[
         IngressItemSpec(host="foo.example.com", pathmappings=[
             IngressPathMappingSpec(path="/", port=80),
             IngressPathMappingSpec(path="/other", port=5000)])],
         ports=[
             PortSpec(protocol="http", name="http", port=80, target_port=8080),
             PortSpec(protocol="http", name="other", port=5000, target_port=8081)]),
     ingress(expose=True, rules=[{
         'host': "foo.example.com",
         'http': {
             'paths': [{
                 'path': '/',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 80,
                 }
             }, {
                 'path': '/other',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 5000,
                 }
             }]
         }
     }, {
         'host': "testapp.svc.test.example.com",
         'http': {
             'paths': [{
                 'path': '/',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 80,
                 }
             }, {
                 'path': '/other',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 5000,
                 }
             }]
         }
     }, {
         'host': "testapp.127.0.0.1.xip.io",
         'http': {
             'paths': [{
                 'path': '/',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 80,
                 }
             }, {
                 'path': '/other',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 5000,
                 }
             }]
         }
     }])),
    ("multiple_explicit_hosts",
     app_spec(ingresses=[
         IngressItemSpec(host="foo.example.com", pathmappings=[IngressPathMappingSpec(path="/", port=80)]),
         IngressItemSpec(host="bar.example.com", pathmappings=[IngressPathMappingSpec(path="/", port=80)])]),
     ingress(expose=True, rules=[{
         'host': "foo.example.com",
         'http': {
             'paths': [{
                 'path': '/',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 80,
                 }
             }]
         }
     }, {
         'host': "bar.example.com",
         'http': {
             'paths': [{
                 'path': '/',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 80,
                 }
             }]
         }
     }, {
         'host': "testapp.svc.test.example.com",
         'http': {
             'paths': [{
                 'path': '/',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 80,
                 }
             }]
         }
     }, {
         'host': "testapp.127.0.0.1.xip.io",
         'http': {
             'paths': [{
                 'path': '/',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 80,
                 }
             }]
         }
     }])),
    ("multiple_explicit_hosts_multiple_paths",
     app_spec(ingresses=[
         IngressItemSpec(host="foo.example.com", pathmappings=[
             IngressPathMappingSpec(path="/one", port=80),
             IngressPathMappingSpec(path="/two", port=5000)
         ]
                         ),
         IngressItemSpec(host="bar.example.com", pathmappings=[
             IngressPathMappingSpec(path="/three", port=80),
             IngressPathMappingSpec(path="/four", port=5000)
         ])],
         ports=[
             PortSpec(protocol="http", name="http", port=80, target_port=8080),
             PortSpec(protocol="http", name="other", port=5000, target_port=8081),
         ]),
     ingress(expose=True, rules=[{
         'host': "foo.example.com",
         'http': {
             'paths': [{
                 'path': '/one',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 80,
                 }
             }, {
                 'path': '/two',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 5000,
                 }
             }]
         }
     }, {
         'host': "bar.example.com",
         'http': {
             'paths': [{
                 'path': '/three',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 80,
                 }
             }, {
                 'path': '/four',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 5000,
                 }
             }]
         }
     }, {
         'host': "testapp.svc.test.example.com",
         'http': {
             'paths': [{
                 'path': '/one',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 80,
                 }
             }, {
                 'path': '/two',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 5000,
                 }
             }, {
                 'path': '/three',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 80,
                 }
             }, {
                 'path': '/four',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 5000,
                 }
             }]
         }
     }, {
         'host': "testapp.127.0.0.1.xip.io",
         'http': {
             'paths': [{
                 'path': '/one',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 80,
                 }
             }, {
                 'path': '/two',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 5000,
                 }
             }, {
                 'path': '/three',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 80,
                 }
             }, {
                 'path': '/four',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 5000,
                 }
             }]
         }
     }])),
    ("rewrite_host_simple",
     app_spec(ingresses=[
         IngressItemSpec(host="rewrite.example.com", pathmappings=[IngressPathMappingSpec(path="/", port=80)])]),
     ingress(expose=True, rules=[{
         'host': "test.rewrite.example.com",
         'http': {
             'paths': [{
                 'path': '/',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 80,
                 }
             }]
         }
     }, {
         'host': "testapp.svc.test.example.com",
         'http': {
             'paths': [{
                 'path': '/',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 80,
                 }
             }]
         }
     }, {
         'host': "testapp.127.0.0.1.xip.io",
         'http': {
             'paths': [{
                 'path': '/',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 80,
                 }
             }]
         }
     }])),
    ("rewrite_host_regex_substitution",
     app_spec(ingresses=[
         IngressItemSpec(host="foo.rewrite.example.com", pathmappings=[IngressPathMappingSpec(path="/", port=80)])]),
     ingress(expose=True, rules=[{
         'host': "test.foo.rewrite.example.com",
         'http': {
             'paths': [{
                 'path': '/',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 80,
                 }
             }]
         }
     }, {
         'host': "testapp.svc.test.example.com",
         'http': {
             'paths': [{
                 'path': '/',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 80,
                 }
             }]
         }
     }, {
         'host': "testapp.127.0.0.1.xip.io",
         'http': {
             'paths': [{
                 'path': '/',
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 80,
                 }
             }]
         }
     }])),
    ("custom_labels_and_annotations",
     app_spec(labels=LabelAndAnnotationSpec(deployment={}, horizontal_pod_autoscaler={},
                                            ingress={"ingress_deployer": "pass through", "custom": "label"},
                                            service={}, pod={}),
              annotations=LabelAndAnnotationSpec(deployment={}, horizontal_pod_autoscaler={},
                                                 ingress={"custom": "annotation"}, service={}, pod={})),
     ingress(metadata=pytest.helpers.create_metadata('testapp', external=False,
                                                     labels={"ingress_deployer": "pass through", "custom": "label"},
                                                     annotations={"fiaas/expose": "false", "custom": "annotation"}))),
    ("regex_path",
     app_spec(ingresses=[
         IngressItemSpec(host=None, pathmappings=[
             IngressPathMappingSpec(
                 path=r"/(foo|bar/|other/(baz|quux)/stuff|foo.html|[1-5][0-9][0-9]$|[1-5][0-9][0-9]\..*$)",
                 port=80)])]),
     ingress(expose=False, rules=[{
         'host': "testapp.svc.test.example.com",
         'http': {
             'paths': [{
                 'path': r"/(foo|bar/|other/(baz|quux)/stuff|foo.html|[1-5][0-9][0-9]$|[1-5][0-9][0-9]\..*$)",
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 80,
                 }
             }]
         }
     }, {
         'host': "testapp.127.0.0.1.xip.io",
         'http': {
             'paths': [{
                 'path': r"/(foo|bar/|other/(baz|quux)/stuff|foo.html|[1-5][0-9][0-9]$|[1-5][0-9][0-9]\..*$)",
                 'backend': {
                     'serviceName': 'testapp',
                     'servicePort': 80,
                 }
             }]
         }
     }])),
)


class TestIngressDeployer(object):
    @pytest.fixture
    def ingress_tls(self, config):
        return mock.create_autospec(IngressTls(config), spec_set=True, instance=True)

    @pytest.fixture
    def config(self):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.ingress_suffixes = ["svc.test.example.com", "127.0.0.1.xip.io"]
        config.host_rewrite_rules = [
            HostRewriteRule("rewrite.example.com=test.rewrite.example.com"),
            HostRewriteRule(r"([a-z0-9](?:[-a-z0-9]*[a-z0-9])?).rewrite.example.com=test.\1.rewrite.example.com")
        ]
        return config

    @pytest.fixture
    def deployer(self, config, ingress_tls):
        return IngressDeployer(config, ingress_tls)

    @pytest.fixture
    def deployer_no_suffix(self, config, ingress_tls):
        config.ingress_suffixes = []
        return IngressDeployer(config, ingress_tls)

    def pytest_generate_tests(self, metafunc):
        fixtures = ("app_spec", "expected_ingress")
        if metafunc.cls == self.__class__ and metafunc.function.__name__ == "test_ingress_deploy" and \
                all(fixname in metafunc.fixturenames for fixname in fixtures):
            for test_id, app_spec, expected_ingress in TEST_DATA:
                params = {"app_spec": app_spec, "expected_ingress": expected_ingress}
                metafunc.addcall(params, test_id)

    @pytest.mark.usefixtures("get")
    def test_ingress_deploy(self, post, deployer, app_spec, expected_ingress):
        mock_response = create_autospec(Response)
        mock_response.json.return_value = expected_ingress
        post.return_value = mock_response

        deployer.deploy(app_spec, LABELS)

        pytest.helpers.assert_any_call(post, INGRESSES_URI, expected_ingress)

    @pytest.mark.parametrize("spec_name", (
            "app_spec_thrift",
            "app_spec_no_ports",
    ))
    def test_remove_existing_ingress_if_not_needed(self, request, delete, post, deployer, spec_name):
        app_spec = request.getfuncargvalue(spec_name)

        deployer.deploy(app_spec, LABELS)

        pytest.helpers.assert_no_calls(post, INGRESSES_URI)
        pytest.helpers.assert_any_call(delete, INGRESSES_URI + "testapp")

    @pytest.mark.usefixtures("get")
    def test_no_ingress(self, delete, post, deployer_no_suffix, app_spec):
        deployer_no_suffix.deploy(app_spec, LABELS)

        pytest.helpers.assert_no_calls(post, INGRESSES_URI)
        pytest.helpers.assert_any_call(delete, INGRESSES_URI + "testapp")

    @pytest.mark.parametrize("app_spec, hosts", (
            (app_spec(), [u'testapp.svc.test.example.com', u'testapp.127.0.0.1.xip.io']),
            (app_spec(ingresses=[
                IngressItemSpec(host="foo.rewrite.example.com",
                                pathmappings=[IngressPathMappingSpec(path="/", port=80)])]),
             [u'testapp.svc.test.example.com', u'testapp.127.0.0.1.xip.io', u'test.foo.rewrite.example.com']),
    ))
    def test_applies_ingress_tls(self, deployer, ingress_tls, app_spec, hosts):
        with mock.patch("k8s.models.ingress.Ingress.get_or_create") as get_or_create:
            get_or_create.return_value = mock.create_autospec(Ingress, spec_set=True)
            deployer.deploy(app_spec, LABELS)
            ingress_tls.apply.assert_called_once_with(IngressMatcher(), app_spec, hosts)


class IngressMatcher(object):
    def __eq__(self, other):
        return isinstance(other, Ingress)


class TestIngressTls(object):
    HOSTS = ["host1", "host2", "host3"]
    COLLAPSED_HOSTS = ["zgwvxk7m22jnzqmofnboadb6kpuri4st.short.suffix"] + HOSTS
    INGRESS_SPEC_TLS = [
        IngressTLS(hosts=["host1"], secretName="host1"),
        IngressTLS(hosts=["host2"], secretName="host2"),
        IngressTLS(hosts=["host3"], secretName="host3"),
        IngressTLS(hosts=COLLAPSED_HOSTS, secretName="testapp-ingress-tls"),
    ]

    @pytest.fixture
    def config(self):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        return config

    @pytest.fixture
    def tls(self, request, config):
        config.use_ingress_tls = request.param["use_ingress_tls"]
        config.tls_certificate_issuer = request.param["cert_issuer"]
        config.ingress_suffixes = ["short.suffix", "really.quite.long.suffix"]
        return IngressTls(config)

    @pytest.mark.parametrize("tls, app_spec, spec_tls, tls_annotations", [
        ({"use_ingress_tls": "default_off", "cert_issuer": None},
         app_spec(ingress_tls=IngressTlsSpec(enabled=True, certificate_issuer=None)),
         INGRESS_SPEC_TLS, {"kubernetes.io/tls-acme": "true"}),
        ({"use_ingress_tls": "default_off", "cert_issuer": None},
         app_spec(ingress_tls=IngressTlsSpec(enabled=False, certificate_issuer=None)), [], None),
        ({"use_ingress_tls": "default_on", "cert_issuer": None},
         app_spec(ingress_tls=IngressTlsSpec(enabled=True, certificate_issuer=None)),
         INGRESS_SPEC_TLS, {"kubernetes.io/tls-acme": "true"}),
        ({"use_ingress_tls": "default_on", "cert_issuer": None},
         app_spec(ingress_tls=IngressTlsSpec(enabled=False, certificate_issuer=None)), [], None),
        ({"use_ingress_tls": "disabled", "cert_issuer": None},
         app_spec(ingress_tls=IngressTlsSpec(enabled=True, certificate_issuer=None)), [], None),
        ({"use_ingress_tls": "disabled", "cert_issuer": None},
         app_spec(ingress_tls=IngressTlsSpec(enabled=False, certificate_issuer=None)), [], None),
        ({"use_ingress_tls": "default_off", "cert_issuer": "letsencrypt"},
         app_spec(ingress_tls=IngressTlsSpec(enabled=True, certificate_issuer=None)),
         INGRESS_SPEC_TLS,
         {"certmanager.k8s.io/cluster-issuer": "letsencrypt"}),
        ({"use_ingress_tls": "default_off", "cert_issuer": "letsencrypt"},
         app_spec(ingress_tls=IngressTlsSpec(enabled=True, certificate_issuer="myoverwrite")),
         INGRESS_SPEC_TLS,
         {"certmanager.k8s.io/cluster-issuer": "myoverwrite"}),
        ({"use_ingress_tls": "default_off", "cert_issuer": None},
         app_spec(ingress_tls=IngressTlsSpec(enabled=True, certificate_issuer="myoverwrite")),
         INGRESS_SPEC_TLS,
         {"certmanager.k8s.io/cluster-issuer": "myoverwrite"}),
    ], indirect=['tls'])
    def test_apply_tls(self, tls, app_spec, spec_tls, tls_annotations):
        ingress = Ingress()
        ingress.metadata = ObjectMeta()
        ingress.spec = IngressSpec()
        tls.apply(ingress, app_spec, self.HOSTS)
        assert ingress.metadata.annotations == tls_annotations
        assert ingress.spec.tls == spec_tls

    @pytest.mark.parametrize("suffix, expected", [
        ("short.suffix", "zgwvxk7m22jnzqmofnboadb6kpuri4st.short.suffix"),
        ("this.is.really.a.quite.extensive.suffix", "zgwvxk7m22jnzqmofnboadb.this.is.really.a.quite.extensive.suffix"),
        ("extremely.long.suffix.which.pushes.the.boundary.to.the.utmost",
         "z.extremely.long.suffix.which.pushes.the.boundary.to.the.utmost"),
    ])
    def test_shorten_name(self, config, suffix, expected):
        config.use_ingress_tls = "default_on"
        config.ingress_suffixes = [suffix]
        tls = IngressTls(config)
        actual = tls._generate_short_host(app_spec())
        assert len(actual) < 64
        assert expected == actual

    def test_raise_when_suffix_too_long(self, config):
        config.use_ingress_tls = "default_on"
        config.ingress_suffixes = ["this.suffix.is.so.long.that.it.is.impossible.to.generate.a.short.enough.name"]
        tls = IngressTls(config)
        with pytest.raises(ValueError):
            tls._generate_short_host(app_spec())

    def test_raise_when_name_starts_with_dot(self, config):
        config.use_ingress_tls = "default_on"
        config.ingress_suffixes = ["really.long.suffix.which.goes.to.the.very.edge.of.the.boundary"]
        tls = IngressTls(config)
        with pytest.raises(ValueError):
            tls._generate_short_host(app_spec())
