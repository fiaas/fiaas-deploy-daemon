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
from dataclasses import dataclass
from unittest import mock
import pytest
from k8s.models.networking_v1_ingress import Ingress, IngressTLS
from unittest.mock import create_autospec, Mock
from requests import Response

from fiaas_deploy_daemon import ExtensionHookCaller
from fiaas_deploy_daemon.config import Configuration, HostRewriteRule
from fiaas_deploy_daemon.deployer.kubernetes.ingress import IngressDeployer, IngressTLSDeployer
from fiaas_deploy_daemon.deployer.kubernetes.ingress_networkingv1 import NetworkingV1IngressAdapter
from fiaas_deploy_daemon.specs.models import (
    AppSpec,
    ResourceRequirementSpec,
    ResourcesSpec,
    PrometheusSpec,
    DatadogSpec,
    PortSpec,
    CheckSpec,
    HttpCheckSpec,
    TcpCheckSpec,
    HealthCheckSpec,
    AutoscalerSpec,
    LabelAndAnnotationSpec,
    IngressItemSpec,
    IngressPathMappingSpec,
    StrongboxSpec,
    IngressTLSSpec,
)

from utils import TypeMatcher

LABELS = {"ingress_deployer": "pass through", "app": "testapp", "fiaas/deployment_id": "12345"}
ANNOTATIONS = {"some/annotation": "val"}
LABEL_SELECTOR_PARAMS = {"labelSelector": "app=testapp,fiaas/deployment_id,fiaas/deployment_id!=12345"}
INGRESSES_URI = "/apis/networking.k8s.io/v1/namespaces/default/ingresses/"
DEFAULT_TLS_ISSUER_TYPE = "certmanager.k8s.io/cluster-issuer"
DEFAULT_TLS_ISSUER = "letsencrypt"
DEFAULT_TLS_ANNOTATIONS = {"certmanager.k8s.io/cluster-issuer": "letsencrypt"}


def app_spec(**kwargs):
    default_app_spec = AppSpec(
        uid="c1f34517-6f54-11ea-8eaf-0ad3d9992c8c",
        name="testapp",
        namespace="default",
        image="finntech/testimage:version",
        autoscaler=AutoscalerSpec(enabled=False, min_replicas=2, max_replicas=3, cpu_threshold_percentage=50),
        resources=ResourcesSpec(
            requests=ResourceRequirementSpec(cpu=None, memory=None),
            limits=ResourceRequirementSpec(cpu=None, memory=None),
        ),
        admin_access=False,
        secrets_in_environment=False,
        prometheus=PrometheusSpec(enabled=True, port="http", path="/internal-backstage/prometheus"),
        datadog=DatadogSpec(enabled=False, tags={}),
        ports=[
            PortSpec(protocol="http", name="http", port=80, target_port=8080),
        ],
        health_checks=HealthCheckSpec(
            liveness=CheckSpec(
                tcp=TcpCheckSpec(port=8080),
                http=None,
                execute=None,
                initial_delay_seconds=10,
                period_seconds=10,
                success_threshold=1,
                failure_threshold=3,
                timeout_seconds=1,
            ),
            readiness=CheckSpec(
                http=HttpCheckSpec(path="/", port=8080, http_headers={}),
                tcp=None,
                execute=None,
                initial_delay_seconds=10,
                period_seconds=10,
                success_threshold=1,
                failure_threshold=3,
                timeout_seconds=1,
            ),
        ),
        teams=["foo"],
        tags=["bar"],
        deployment_id="test_app_deployment_id",
        labels=LabelAndAnnotationSpec({}, {}, {}, {}, {}, {}, {}),
        annotations=LabelAndAnnotationSpec({}, {}, ANNOTATIONS.copy(), {}, {}, {}, {}),
        ingresses=[
            IngressItemSpec(host=None, pathmappings=[IngressPathMappingSpec(path="/", port=80)], annotations={})
        ],
        strongbox=StrongboxSpec(enabled=False, iam_role=None, aws_region="eu-west-1", groups=None),
        singleton=False,
        ingress_tls=IngressTLSSpec(enabled=False, certificate_issuer=None),
        secrets=[],
        app_config={},
    )

    return default_app_spec._replace(**kwargs)


def _create_rule(host, paths=None):
    rule = {
        "host": host,
        "http": {
            "paths": [
                {
                    "path": "/",
                    "pathType": "ImplementationSpecific",
                    "backend": {
                        "service": {
                            "name": "testapp",
                            "port": {
                                "number": 80,
                            },
                        },
                    },
                }
            ]
        },
    }
    if paths:
        rule["http"]["paths"] = paths
    return rule


def _create_path(path, svc, port):
    return {
        "path": path,
        "pathType": "ImplementationSpecific",
        "backend": {
            "service": {
                "name": svc,
                "port": {
                    "number": port,
                },
            },
        },
    }


def ingress(rules=None, metadata=None, expose=False, tls=None):
    default_rules = [
        _create_rule("testapp.svc.test.example.com"),
        _create_rule("testapp.127.0.0.1.xip.io"),
    ]
    default_metadata = pytest.helpers.create_metadata(
        "testapp", labels=LABELS, annotations=ANNOTATIONS, external=expose
    )

    expected_ingress = {
        "spec": {"rules": rules if rules else default_rules, "tls": tls if tls else []},
        "metadata": metadata if metadata else default_metadata,
    }
    return expected_ingress


@dataclass
class IngressTestcase:
    test_id: str
    app_spec: AppSpec
    expected_ingress: dict


TEST_DATA = (
    IngressTestcase("only_default_hosts", app_spec(), ingress()),
    IngressTestcase(
        "single_explicit_host",
        app_spec(
            ingresses=[
                IngressItemSpec(
                    host="foo.example.com", pathmappings=[IngressPathMappingSpec(path="/", port=80)], annotations={}
                )
            ]
        ),
        ingress(
            expose=True,
            rules=[
                _create_rule("foo.example.com"),
                _create_rule("testapp.svc.test.example.com"),
                _create_rule("testapp.127.0.0.1.xip.io"),
            ],
        ),
    ),
    IngressTestcase(
        "single_explicit_host_multiple_paths",
        app_spec(
            ingresses=[
                IngressItemSpec(
                    host="foo.example.com",
                    pathmappings=[
                        IngressPathMappingSpec(path="/", port=80),
                        IngressPathMappingSpec(path="/other", port=5000),
                    ],
                    annotations={},
                )
            ],
            ports=[
                PortSpec(protocol="http", name="http", port=80, target_port=8080),
                PortSpec(protocol="http", name="other", port=5000, target_port=8081),
            ],
        ),
        ingress(
            expose=True,
            rules=[
                _create_rule(
                    "foo.example.com", paths=[_create_path("/", "testapp", 80), _create_path("/other", "testapp", 5000)]
                ),
                _create_rule(
                    "testapp.svc.test.example.com",
                    paths=[_create_path("/", "testapp", 80), _create_path("/other", "testapp", 5000)],
                ),
                _create_rule(
                    "testapp.127.0.0.1.xip.io",
                    paths=[_create_path("/", "testapp", 80), _create_path("/other", "testapp", 5000)],
                ),
            ],
        ),
    ),
    IngressTestcase(
        "multiple_explicit_hosts",
        app_spec(
            ingresses=[
                IngressItemSpec(
                    host="foo.example.com", pathmappings=[IngressPathMappingSpec(path="/", port=80)], annotations={}
                ),
                IngressItemSpec(
                    host="bar.example.com", pathmappings=[IngressPathMappingSpec(path="/", port=80)], annotations={}
                ),
            ]
        ),
        ingress(
            expose=True,
            rules=[
                _create_rule("foo.example.com"),
                _create_rule("bar.example.com"),
                _create_rule("testapp.svc.test.example.com"),
                _create_rule("testapp.127.0.0.1.xip.io"),
            ],
        ),
    ),
    IngressTestcase(
        "multiple_explicit_hosts_multiple_paths",
        app_spec(
            ingresses=[
                IngressItemSpec(
                    host="foo.example.com",
                    pathmappings=[
                        IngressPathMappingSpec(path="/one", port=80),
                        IngressPathMappingSpec(path="/two", port=5000),
                    ],
                    annotations={},
                ),
                IngressItemSpec(
                    host="bar.example.com",
                    pathmappings=[
                        IngressPathMappingSpec(path="/three", port=80),
                        IngressPathMappingSpec(path="/four", port=5000),
                    ],
                    annotations={},
                ),
            ],
            ports=[
                PortSpec(protocol="http", name="http", port=80, target_port=8080),
                PortSpec(protocol="http", name="other", port=5000, target_port=8081),
            ],
        ),
        ingress(
            expose=True,
            rules=[
                _create_rule(
                    "foo.example.com",
                    paths=[
                        _create_path("/one", "testapp", 80),
                        _create_path("/two", "testapp", 5000),
                    ],
                ),
                _create_rule(
                    "bar.example.com",
                    paths=[
                        _create_path("/three", "testapp", 80),
                        _create_path("/four", "testapp", 5000),
                    ],
                ),
                _create_rule(
                    "testapp.svc.test.example.com",
                    paths=[
                        _create_path("/one", "testapp", 80),
                        _create_path("/two", "testapp", 5000),
                        _create_path("/three", "testapp", 80),
                        _create_path("/four", "testapp", 5000),
                    ],
                ),
                _create_rule(
                    "testapp.127.0.0.1.xip.io",
                    paths=[
                        _create_path("/one", "testapp", 80),
                        _create_path("/two", "testapp", 5000),
                        _create_path("/three", "testapp", 80),
                        _create_path("/four", "testapp", 5000),
                    ],
                ),
            ],
        ),
    ),
    IngressTestcase(
        "rewrite_host_simple",
        app_spec(
            ingresses=[
                IngressItemSpec(
                    host="rewrite.example.com", pathmappings=[IngressPathMappingSpec(path="/", port=80)], annotations={}
                )
            ]
        ),
        ingress(
            expose=True,
            rules=[
                _create_rule("test.rewrite.example.com"),
                _create_rule("testapp.svc.test.example.com"),
                _create_rule("testapp.127.0.0.1.xip.io"),
            ],
        ),
    ),
    IngressTestcase(
        "rewrite_host_regex_substitution",
        app_spec(
            ingresses=[
                IngressItemSpec(
                    host="foo.rewrite.example.com",
                    pathmappings=[IngressPathMappingSpec(path="/", port=80)],
                    annotations={},
                )
            ]
        ),
        ingress(
            expose=True,
            rules=[
                _create_rule("test.foo.rewrite.example.com"),
                _create_rule("testapp.svc.test.example.com"),
                _create_rule("testapp.127.0.0.1.xip.io"),
            ],
        ),
    ),
    IngressTestcase(
        "custom_labels_and_annotations",
        app_spec(
            labels=LabelAndAnnotationSpec(
                deployment={},
                horizontal_pod_autoscaler={},
                ingress={"ingress_deployer": "pass through", "custom": "label"},
                service={},
                service_account={},
                pod={},
                status={},
            ),
            annotations=LabelAndAnnotationSpec(
                deployment={},
                horizontal_pod_autoscaler={},
                ingress={"custom": "annotation"},
                service={},
                service_account={},
                pod={},
                status={},
            ),
        ),
        ingress(
            metadata=pytest.helpers.create_metadata(
                "testapp",
                external=False,
                labels={
                    "ingress_deployer": "pass through",
                    "custom": "label",
                    "app": "testapp",
                    "fiaas/deployment_id": "12345",
                },
                annotations={"fiaas/expose": "false", "custom": "annotation"},
            )
        ),
    ),
    IngressTestcase(
        "regex_path",
        app_spec(
            ingresses=[
                IngressItemSpec(
                    host=None,
                    pathmappings=[
                        IngressPathMappingSpec(
                            path=r"/(foo|bar/|other/(baz|quux)/stuff|foo.html|[1-5][0-9][0-9]$|[1-5][0-9][0-9]\..*$)",
                            port=80,
                        )
                    ],
                    annotations={},
                )
            ]
        ),
        ingress(
            expose=False,
            rules=[
                _create_rule(
                    "testapp.svc.test.example.com",
                    paths=[
                        _create_path(
                            r"/(foo|bar/|other/(baz|quux)/stuff|foo.html|[1-5][0-9][0-9]$|[1-5][0-9][0-9]\..*$)",
                            "testapp",
                            80,
                        ),
                    ],
                ),
                _create_rule(
                    "testapp.127.0.0.1.xip.io",
                    paths=[
                        _create_path(
                            r"/(foo|bar/|other/(baz|quux)/stuff|foo.html|[1-5][0-9][0-9]$|[1-5][0-9][0-9]\..*$)",
                            "testapp",
                            80,
                        ),
                    ],
                ),
            ],
        ),
    ),
)


class TestIngressDeployer(object):
    @pytest.fixture
    def extension_hook(self):
        return mock.create_autospec(ExtensionHookCaller, spec_set=True, instance=True)

    @pytest.fixture
    def ingress_tls_deployer(self, config):
        return mock.create_autospec(IngressTLSDeployer(config, IngressTLS), spec_set=True, instance=True)

    @pytest.fixture
    def config(self):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.ingress_suffixes = ["svc.test.example.com", "127.0.0.1.xip.io"]
        config.host_rewrite_rules = [
            HostRewriteRule("rewrite.example.com=test.rewrite.example.com"),
            HostRewriteRule(r"([a-z0-9](?:[-a-z0-9]*[a-z0-9])?).rewrite.example.com=test.\1.rewrite.example.com"),
            HostRewriteRule(r"([\w\.\-]+)\.svc.test.example.com=dont-rewrite-suffix-urls.example.com"),
            HostRewriteRule(r"([\w\.\-]+)\.127.0.0.1.xip.io=dont-rewrite-suffix-urls.example.com"),
        ]
        config.tls_certificate_issuer_type_default = DEFAULT_TLS_ISSUER_TYPE
        config.tls_certificate_issuer = DEFAULT_TLS_ISSUER
        config.tls_certificate_issuer_type_overrides = {}
        config.tls_certificate_issuer_overrides = {}
        return config

    @pytest.fixture
    def ingress_adapter(self, ingress_tls_deployer, owner_references, extension_hook):
        return NetworkingV1IngressAdapter(ingress_tls_deployer, owner_references, extension_hook)

    @pytest.fixture
    def deployer(self, config, default_app_spec, ingress_adapter):
        return IngressDeployer(config, default_app_spec, ingress_adapter)

    @pytest.fixture
    def deployer_no_suffix(self, config, default_app_spec, ingress_adapter):
        config.ingress_suffixes = []
        return IngressDeployer(config, default_app_spec, ingress_adapter)

    @pytest.fixture
    def default_app_spec(self):
        default_app_spec = Mock(return_value=app_spec())
        return default_app_spec

    @pytest.mark.parametrize("testcase", TEST_DATA, ids=lambda itc: itc.test_id)
    @pytest.mark.usefixtures("get")
    def test_ingress_deploy(self, post, delete, deployer, owner_references, extension_hook, testcase):
        mock_response = create_autospec(Response)
        mock_response.json.return_value = testcase.expected_ingress
        post.return_value = mock_response

        deployer.deploy(testcase.app_spec, LABELS)

        pytest.helpers.assert_any_call(post, INGRESSES_URI, testcase.expected_ingress)
        owner_references.apply.assert_called_once_with(TypeMatcher(Ingress), testcase.app_spec)
        extension_hook.apply.assert_called_once_with(TypeMatcher(Ingress), testcase.app_spec)
        delete.assert_called_once_with(INGRESSES_URI, body=None, params=LABEL_SELECTOR_PARAMS)

    @pytest.fixture
    def dtparse(self):
        with mock.patch("pyrfc3339.parse") as m:
            yield m

    @pytest.mark.usefixtures("dtparse", "get")
    def test_multiple_ingresses(self, post, delete, deployer, app_spec):
        app_spec.annotations.ingress.update(ANNOTATIONS.copy())

        del app_spec.ingresses[:]  # make sure the default ingress will be re-created
        app_spec.ingresses.append(
            IngressItemSpec(
                host="extra.example.com",
                pathmappings=[IngressPathMappingSpec(path="/", port=8000)],
                annotations={"some/annotation": "some-value"},
            )
        )
        app_spec.ingresses.append(
            IngressItemSpec(
                host="extra.example.com",
                pathmappings=[IngressPathMappingSpec(path="/_/ipblocked", port=8000)],
                annotations={"some/allowlist": "10.0.0.1/12"},
            )
        )

        expected_ingress = ingress()
        mock_response = create_autospec(Response)
        mock_response.json.return_value = expected_ingress

        expected_metadata2 = pytest.helpers.create_metadata(
            "testapp-1", labels=LABELS, annotations={"some/annotation": "some-value"}, external=True
        )
        expected_ingress2 = ingress(
            rules=[_create_rule("extra.example.com", paths=[_create_path("/", app_spec.name, 8000)])],
            metadata=expected_metadata2,
        )
        mock_response2 = create_autospec(Response)
        mock_response.json.return_value = expected_ingress2

        expected_metadata3 = pytest.helpers.create_metadata(
            "testapp-2",
            labels=LABELS,
            annotations={"some/annotation": "val", "some/allowlist": "10.0.0.1/12"},
            external=True,
        )
        expected_ingress3 = ingress(
            rules=[_create_rule("extra.example.com", paths=[_create_path("/_/ipblocked", app_spec.name, 8000)])],
            metadata=expected_metadata3,
        )
        mock_response3 = create_autospec(Response)
        mock_response3.json.return_value = expected_ingress3

        post.side_effect = iter([mock_response, mock_response2, mock_response3])

        deployer.deploy(app_spec, LABELS)

        post.assert_has_calls(
            [
                mock.call(INGRESSES_URI, expected_ingress),
                mock.call(INGRESSES_URI, expected_ingress2),
                mock.call(INGRESSES_URI, expected_ingress3),
            ]
        )
        delete.assert_called_once_with(INGRESSES_URI, body=None, params=LABEL_SELECTOR_PARAMS)

    @pytest.mark.parametrize(
        "spec_name",
        (
            "app_spec_thrift",
            "app_spec_no_ports",
        ),
    )
    def test_remove_existing_ingress_if_not_needed(self, request, delete, post, deployer, spec_name):
        app_spec = request.getfixturevalue(spec_name)

        deployer.deploy(app_spec, LABELS)

        pytest.helpers.assert_no_calls(post, INGRESSES_URI)
        pytest.helpers.assert_any_call(delete, INGRESSES_URI, body=None, params=LABEL_SELECTOR_PARAMS)

    @pytest.mark.usefixtures("get")
    def test_no_ingress(self, delete, post, deployer_no_suffix, app_spec):
        deployer_no_suffix.deploy(app_spec, LABELS)

        pytest.helpers.assert_no_calls(post, INGRESSES_URI)
        pytest.helpers.assert_any_call(delete, INGRESSES_URI, body=None, params=LABEL_SELECTOR_PARAMS)

    @pytest.mark.parametrize(
        "app_spec, hosts",
        (
            (app_spec(), ["testapp.svc.test.example.com", "testapp.127.0.0.1.xip.io"]),
            (
                app_spec(
                    ingresses=[
                        IngressItemSpec(
                            host="foo.rewrite.example.com",
                            pathmappings=[IngressPathMappingSpec(path="/", port=80)],
                            annotations={},
                        )
                    ]
                ),
                ["test.foo.rewrite.example.com", "testapp.svc.test.example.com", "testapp.127.0.0.1.xip.io"],
            ),
        ),
    )
    @pytest.mark.usefixtures("delete")
    def test_applies_ingress_tls_deployer(self, deployer, ingress_tls_deployer, app_spec, hosts):
        with mock.patch("k8s.models.networking_v1_ingress.Ingress.get_or_create") as get_or_create:
            get_or_create.return_value = mock.create_autospec(Ingress, spec_set=True)
            deployer.deploy(app_spec, LABELS)
            ingress_tls_deployer.apply.assert_called_once_with(
                TypeMatcher(Ingress), app_spec, hosts, DEFAULT_TLS_ISSUER_TYPE, DEFAULT_TLS_ISSUER, use_suffixes=True
            )

    @pytest.fixture
    def deployer_issuer_overrides(self, config, default_app_spec, ingress_adapter):
        config.tls_certificate_issuer_type_overrides = {
            "foo.example.com": "certmanager.k8s.io/issuer",
            "bar.example.com": "certmanager.k8s.io/cluster-issuer",
            "foo.bar.example.com": "certmanager.k8s.io/issuer",
        }
        return IngressDeployer(config, default_app_spec, ingress_adapter)

    @pytest.mark.usefixtures("delete")
    def test_applies_ingress_tls_deployer_issuer_overrides(
        self, post, deployer_issuer_overrides, ingress_tls_deployer, app_spec
    ):
        with mock.patch("k8s.models.networking_v1_ingress.Ingress.get_or_create") as get_or_create:
            get_or_create.return_value = mock.create_autospec(Ingress, spec_set=True)
            app_spec.ingresses[:] = [
                # has issuer-override
                IngressItemSpec(
                    host="foo.example.com", pathmappings=[IngressPathMappingSpec(path="/", port=80)], annotations={}
                ),
                # no issuer-override
                IngressItemSpec(
                    host="bar.example.com", pathmappings=[IngressPathMappingSpec(path="/", port=80)], annotations={}
                ),
                IngressItemSpec(
                    host="foo.bar.example.com", pathmappings=[IngressPathMappingSpec(path="/", port=80)], annotations={}
                ),
                IngressItemSpec(
                    host="other.example.com", pathmappings=[IngressPathMappingSpec(path="/", port=80)], annotations={}
                ),
                # suffix has issuer-override
                IngressItemSpec(
                    host="sub.foo.example.com", pathmappings=[IngressPathMappingSpec(path="/", port=80)], annotations={}
                ),
                # more specific suffix has issuer-override
                IngressItemSpec(
                    host="sub.bar.example.com", pathmappings=[IngressPathMappingSpec(path="/", port=80)], annotations={}
                ),
                # has annotations
                IngressItemSpec(
                    host="ann.foo.example.com",
                    pathmappings=[IngressPathMappingSpec(path="/", port=80)],
                    annotations={"some": "annotation"},
                ),
            ]

            deployer_issuer_overrides.deploy(app_spec, LABELS)
            host_groups = [sorted(call.args[2]) for call in ingress_tls_deployer.apply.call_args_list]
            ingress_names = [call.kwargs["metadata"].name for call in get_or_create.call_args_list]
            expected_host_groups = [
                ["ann.foo.example.com"],
                [
                    "bar.example.com",
                    "other.example.com",
                    "sub.bar.example.com",
                    "testapp.127.0.0.1.xip.io",
                    "testapp.svc.test.example.com",
                ],
                ["foo.bar.example.com", "foo.example.com", "sub.foo.example.com"],
            ]
            expected_ingress_names = ["testapp", "testapp-1", "testapp-2"]
            assert ingress_tls_deployer.apply.call_count == 3
            assert expected_host_groups == sorted(host_groups)
            assert expected_ingress_names == sorted(ingress_names)
