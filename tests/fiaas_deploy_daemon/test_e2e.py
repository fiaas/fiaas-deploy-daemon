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


import os
import subprocess
import sys
import time

import pytest
import requests
from k8s import config
from k8s.client import NotFound, Client
from k8s.models.autoscaler import HorizontalPodAutoscaler
from k8s.models.common import ObjectMeta
from k8s.models.deployment import Deployment
from k8s.models.ingress import Ingress
from k8s.models.networking_v1_ingress import Ingress as NetworkingV1Ingress
from k8s.models.service import Service
from k8s.models.service_account import ServiceAccount
from utils import (
    wait_until,
    crd_available,
    read_yml,
    sanitize_resource_name,
    assert_k8s_resource_matches,
    get_unbound_port,
    KindWrapper,
    uuid,
    use_networkingv1_ingress,
    use_apiextensionsv1_crd,
)

from fiaas_deploy_daemon.crd.status import create_name
from fiaas_deploy_daemon.crd.types import (
    FiaasApplication,
    FiaasApplicationStatus,
    FiaasApplicationSpec,
    AdditionalLabelsOrAnnotations,
)
from fiaas_deploy_daemon.tools import merge_dicts

IMAGE1 = "finntech/application-name:123"
IMAGE2 = "finntech/application-name:321"
DEPLOYMENT_ID1 = "deployment_id_1"
DEPLOYMENT_ID2 = "deployment_id_2"
PATIENCE = 60
TIMEOUT = 5
SHOULD_NOT_EXIST = object()  # Mapped to Kinds that should not exist in a test case


def _fixture_names(fixture_value):
    return fixture_value[0]


@pytest.mark.integration_test
class TestE2E(object):
    @pytest.fixture(scope="module", params=("ClusterIP", "NodePort"))
    def service_type(self, request):
        return request.param

    @pytest.fixture(scope="module")
    def kubernetes(self, service_type, k8s_version):
        try:
            name = "kind-{}-{}-{}".format(k8s_version, service_type.lower(), uuid())
            kind = KindWrapper(k8s_version, name)
            try:
                yield kind.start()
            finally:
                kind.delete()
        except Exception as e:
            msg = "Unable to run kind: %s"
            pytest.fail(msg % str(e))

    @pytest.fixture(scope="module")
    def kubernetes_service_account(self, k8s_version):
        try:
            name = "kind-{}-{}-{}".format(k8s_version, "sa", uuid())
            kind = KindWrapper(k8s_version, name)
            try:
                yield kind.start()
            finally:
                kind.delete()
        except Exception as e:
            msg = "Unable to run kind: %s"
            pytest.fail(msg % str(e))

    @pytest.fixture()
    def k8s_client(self, kubernetes):
        Client.clear_session()
        config.api_server = kubernetes["host-to-container-server"]
        config.debug = True
        config.verify_ssl = False
        config.cert = (kubernetes["client-cert"], kubernetes["client-key"])

    @pytest.fixture()
    def k8s_client_service_account(self, kubernetes_service_account):
        Client.clear_session()
        config.api_server = kubernetes_service_account["host-to-container-server"]
        config.debug = True
        config.verify_ssl = False
        config.cert = (kubernetes_service_account["client-cert"], kubernetes_service_account["client-key"])

    @pytest.fixture(scope="module")
    def fdd(self, request, kubernetes, service_type, k8s_version, use_docker_for_e2e):
        args, port, ready = self.prepare_fdd(request, kubernetes, k8s_version, use_docker_for_e2e, service_type)
        try:
            daemon = subprocess.Popen(args, stdout=sys.stderr, env=merge_dicts(os.environ, {"NAMESPACE": "default"}))
            time.sleep(1)
            if daemon.poll() is not None:
                pytest.fail("fiaas-deploy-daemon has crashed after startup, inspect logs")
            self.wait_until_fdd_ready(k8s_version, kubernetes, ready)
            yield "http://localhost:{}/fiaas".format(port)
        finally:
            self._end_popen(daemon)

    @pytest.fixture(scope="module")
    def fdd_service_account(self, request, kubernetes_service_account, k8s_version, use_docker_for_e2e):
        args, port, ready = self.prepare_fdd(
            request, kubernetes_service_account, k8s_version, use_docker_for_e2e, "ClusterIP", service_account=True
        )
        try:
            daemon = subprocess.Popen(args, stdout=sys.stderr, env=merge_dicts(os.environ, {"NAMESPACE": "default"}))
            time.sleep(1)
            if daemon.poll() is not None:
                pytest.fail("fiaas-deploy-daemon has crashed after startup, inspect logs")
            self.wait_until_fdd_ready(k8s_version, kubernetes_service_account, ready)
            yield "http://localhost:{}/fiaas".format(port)
        finally:
            self._end_popen(daemon)

    def wait_until_fdd_ready(self, k8s_version, kubernetes, ready):
        wait_until(ready, "web-interface healthy", RuntimeError, patience=PATIENCE)
        wait_until(crd_available(kubernetes, timeout=TIMEOUT), "CRD available", RuntimeError, patience=PATIENCE)

    def prepare_fdd(self, request, kubernetes, k8s_version, use_docker_for_e2e, service_type, service_account=False):
        port = get_unbound_port()
        cert_path = os.path.dirname(kubernetes["api-cert"])
        docker_args = use_docker_for_e2e(
            request, cert_path, service_type, k8s_version, port, kubernetes["container-to-container-server-ip"]
        )
        server = kubernetes["container-to-container-server"] if docker_args else kubernetes["host-to-container-server"]
        args = [
            "fiaas-deploy-daemon",
            "--port",
            str(port),
            "--api-server",
            server,
            "--api-cert",
            kubernetes["api-cert"],
            "--client-cert",
            kubernetes["client-cert"],
            "--client-key",
            kubernetes["client-key"],
            "--service-type",
            service_type,
            "--ingress-suffix",
            "svc.test.example.com",
            "--environment",
            "test",
            "--datadog-container-image",
            "DATADOG_IMAGE:tag",
            "--strongbox-init-container-image",
            "STRONGBOX_IMAGE",
            "--secret-init-containers",
            "parameter-store=PARAM_STORE_IMAGE",
            "--tls-certificate-issuer-type-overrides",
            "use-issuer.example.com=certmanager.k8s.io/issuer",
            "--use-ingress-tls",
            "default_off",
            "--enable-crd-support"
        ]
        if service_account:
            args.append("--enable-service-account-per-app")
        if use_apiextensionsv1_crd(k8s_version):
            args.append("--use-apiextensionsv1-crd")
            args.append("--include-status-in-app")
        if use_networkingv1_ingress(k8s_version):
            args.append("--use-networkingv1-ingress")
        args = docker_args + args

        def ready():
            resp = requests.get("http://localhost:{}/healthz".format(port), timeout=TIMEOUT)
            resp.raise_for_status()

        return args, port, ready

    @pytest.fixture(
        ids=_fixture_names,
        params=(
            (
                "data/v2minimal.yml",
                {
                    Service: "e2e_expected/v2minimal-service.yml",
                    Deployment: "e2e_expected/v2minimal-deployment.yml",
                    Ingress: "e2e_expected/v2minimal-ingress.yml",
                    NetworkingV1Ingress: "e2e_expected/v2minimal-networkingv1-ingress.yml",
                    ServiceAccount: SHOULD_NOT_EXIST,
                },
            ),
            (
                "v2/data/examples/host.yml",
                {
                    Service: "e2e_expected/host-service.yml",
                    Deployment: "e2e_expected/host-deployment.yml",
                    Ingress: "e2e_expected/host-ingress.yml",
                    NetworkingV1Ingress: "e2e_expected/host-networkingv1-ingress.yml",
                },
            ),
            (
                "v2/data/examples/exec_config.yml",
                {
                    Service: "e2e_expected/exec-service.yml",
                    Deployment: "e2e_expected/exec-deployment.yml",
                    Ingress: "e2e_expected/exec-ingress.yml",
                    NetworkingV1Ingress: "e2e_expected/exec-networkingv1-ingress.yml",
                },
            ),
            (
                "v2/data/examples/tcp_ports.yml",
                {
                    Service: "e2e_expected/tcp_ports-service.yml",
                    Deployment: "e2e_expected/tcp_ports-deployment.yml",
                },
            ),
            (
                "v2/data/examples/single_tcp_port.yml",
                {
                    Service: "e2e_expected/single_tcp_port-service.yml",
                    Deployment: "e2e_expected/single_tcp_port-deployment.yml",
                },
            ),
            (
                "v2/data/examples/partial_override.yml",
                {
                    Service: "e2e_expected/partial_override-service.yml",
                    Deployment: "e2e_expected/partial_override-deployment.yml",
                    Ingress: "e2e_expected/partial_override-ingress.yml",
                    NetworkingV1Ingress: "e2e_expected/partial_override-networkingv1-ingress.yml",
                    HorizontalPodAutoscaler: "e2e_expected/partial_override-hpa.yml",
                },
            ),
            (
                "v3/data/examples/v3minimal.yml",
                {
                    Service: "e2e_expected/v3minimal-service.yml",
                    Deployment: "e2e_expected/v3minimal-deployment.yml",
                    Ingress: "e2e_expected/v3minimal-ingress.yml",
                    NetworkingV1Ingress: "e2e_expected/v3minimal-networkingv1-ingress.yml",
                    HorizontalPodAutoscaler: "e2e_expected/v3minimal-hpa.yml",
                    ServiceAccount: SHOULD_NOT_EXIST,
                },
                AdditionalLabelsOrAnnotations(
                    _global={"global/label": "true"},
                    deployment={"deployment/label": "true"},
                    horizontal_pod_autoscaler={"horizontal-pod-autoscaler/label": "true"},
                    ingress={"ingress/label": "true"},
                    service={"service/label": "true"},
                    pod={"pod/label": "true"},
                    status={"status/label": "true"},
                ),
            ),
            (
                "v3/data/examples/full.yml",
                {
                    Service: "e2e_expected/v3full-service.yml",
                    Deployment: "e2e_expected/v3full-deployment.yml",
                    Ingress: "e2e_expected/v3full-ingress.yml",
                    NetworkingV1Ingress: "e2e_expected/v3full-networkingv1-ingress.yml",
                    HorizontalPodAutoscaler: "e2e_expected/v3full-hpa.yml",
                },
                AdditionalLabelsOrAnnotations(
                    _global={"global/label": "true"},
                    deployment={"deployment/label": "true"},
                    horizontal_pod_autoscaler={"horizontal-pod-autoscaler/label": "true"},
                    ingress={"ingress/label": "true"},
                    service={"service/label": "true"},
                    pod={"pod/label": "true", "s": "override"},
                    status={"status/label": "true"},
                ),
            ),
            (
                "v3/data/examples/multiple_hosts_multiple_paths.yml",
                {
                    Service: "e2e_expected/multiple_hosts_multiple_paths-service.yml",
                    Deployment: "e2e_expected/multiple_hosts_multiple_paths-deployment.yml",
                    Ingress: "e2e_expected/multiple_hosts_multiple_paths-ingress.yml",
                    NetworkingV1Ingress: "e2e_expected/multiple_hosts_multiple_paths-networkingv1-ingress.yml",
                    HorizontalPodAutoscaler: "e2e_expected/multiple_hosts_multiple_paths-hpa.yml",
                },
            ),
            (
                "v3/data/examples/strongbox.yml",
                {
                    Service: "e2e_expected/strongbox-service.yml",
                    Deployment: "e2e_expected/strongbox-deployment.yml",
                    Ingress: "e2e_expected/strongbox-ingress.yml",
                    NetworkingV1Ingress: "e2e_expected/strongbox-networkingv1-ingress.yml",
                    HorizontalPodAutoscaler: "e2e_expected/strongbox-hpa.yml",
                },
            ),
            (
                "v3/data/examples/secrets.yml",
                {
                    Deployment: "e2e_expected/secrets-deployment.yml",
                },
            ),
            (
                "v3/data/examples/single-replica-singleton.yml",
                {
                    Deployment: "e2e_expected/single-replica-singleton.yml",
                },
            ),
            (
                "v3/data/examples/single-replica-not-singleton.yml",
                {
                    Deployment: "e2e_expected/single-replica-not-singleton.yml",
                },
            ),
            (
                "v3/data/examples/tls_enabled.yml",
                {
                    Service: "e2e_expected/tls-service.yml",
                    Deployment: "e2e_expected/tls-deployment.yml",
                    Ingress: "e2e_expected/tls-ingress.yml",
                    NetworkingV1Ingress: "e2e_expected/tls-networkingv1-ingress.yml",
                    HorizontalPodAutoscaler: "e2e_expected/tls-hpa.yml",
                },
            ),
            (
                "v3/data/examples/tls_enabled_cert_issuer.yml",
                {
                    Service: "e2e_expected/tls-service-cert-issuer.yml",
                    Deployment: "e2e_expected/tls-deployment-cert-issuer.yml",
                    Ingress: "e2e_expected/tls-ingress-cert-issuer.yml",
                    NetworkingV1Ingress: "e2e_expected/tls-networkingv1-ingress-cert-issuer.yml",
                    HorizontalPodAutoscaler: "e2e_expected/tls-hpa-cert-issuer.yml",
                },
            ),
            (
                "v3/data/examples/tls_enabled_multiple.yml",
                {
                    Ingress: "e2e_expected/tls-ingress-multiple.yml",
                    NetworkingV1Ingress: "e2e_expected/tls-networkingv1-ingress-multiple.yml",
                },
            ),
        ),
    )
    def custom_resource_definition(self, request, k8s_version):
        fiaas_path, expected, additional_labels = self._resource_labels(request.param)

        if use_networkingv1_ingress(k8s_version) and expected.get(Ingress):
            del expected[Ingress]
        elif expected.get(NetworkingV1Ingress):
            del expected[NetworkingV1Ingress]
        fiaas_yml = read_yml(request.fspath.dirpath().join("specs").join(fiaas_path).strpath)
        expected = self._construct_expected(expected, request)

        name, metadata, spec = self._resource_components(fiaas_path, fiaas_yml, additional_labels)
        request.addfinalizer(lambda: self._ensure_clean(name, expected))
        return name, FiaasApplication(metadata=metadata, spec=spec), expected

    @pytest.fixture(
        ids=_fixture_names,
        params=(
            (
                "data/v2minimal.yml",
                {
                    Service: "e2e_expected/v2minimal-service.yml",
                    Deployment: "e2e_expected/v2minimal-deployment.yml",
                    Ingress: "e2e_expected/v2minimal-ingress.yml",
                    NetworkingV1Ingress: "e2e_expected/v2minimal-networkingv1-ingress.yml",
                    ServiceAccount: "e2e_expected/v2minimal-service-account.yml",
                },
            ),
            (
                "v3/data/examples/v3minimal.yml",
                {
                    Service: "e2e_expected/v3minimal-service.yml",
                    Deployment: "e2e_expected/v3minimal-deployment.yml",
                    Ingress: "e2e_expected/v3minimal-ingress.yml",
                    NetworkingV1Ingress: "e2e_expected/v3minimal-networkingv1-ingress.yml",
                    HorizontalPodAutoscaler: "e2e_expected/v3minimal-hpa.yml",
                    ServiceAccount: "e2e_expected/v3minimal-service-account.yml",
                },
                AdditionalLabelsOrAnnotations(
                    _global={"global/label": "true"},
                    deployment={"deployment/label": "true"},
                    horizontal_pod_autoscaler={"horizontal-pod-autoscaler/label": "true"},
                    ingress={"ingress/label": "true"},
                    service={"service/label": "true"},
                    pod={"pod/label": "true"},
                    status={"status/label": "true"},
                ),
            ),
        ),
    )
    def custom_resource_definition_service_account(self, request, k8s_version):
        fiaas_path, expected, additional_labels = self._resource_labels(request.param)

        if use_networkingv1_ingress(k8s_version) and expected.get(Ingress):
            del expected[Ingress]
        elif expected.get(NetworkingV1Ingress):
            del expected[NetworkingV1Ingress]
        fiaas_yml = read_yml(request.fspath.dirpath().join("specs").join(fiaas_path).strpath)
        expected = self._construct_expected(expected, request)

        # modify the expected service account for this test
        for k, _ in list(expected.items()):
            if expected[k]["kind"] == "Deployment":
                name = expected[k]["metadata"]["name"]
                expected[k]["spec"]["template"]["spec"]["serviceAccountName"] = name
                break

        name, metadata, spec = self._resource_components(fiaas_path, fiaas_yml, additional_labels)
        request.addfinalizer(lambda: self._ensure_clean(name, expected))
        return name, FiaasApplication(metadata=metadata, spec=spec), expected

    def _construct_expected(self, expected, request):
        new_expected = {}
        for kind, path in list(expected.items()):
            if path == SHOULD_NOT_EXIST:
                new_expected[kind] = SHOULD_NOT_EXIST
            else:
                new_expected[kind] = read_yml(request.fspath.dirpath().join(path).strpath)
        return new_expected

    def _resource_components(self, fiaas_path, fiaas_yml, additional_labels):
        name = sanitize_resource_name(fiaas_path)
        metadata = ObjectMeta(name=name, namespace="default", labels={"fiaas/deployment_id": DEPLOYMENT_ID1})
        spec = FiaasApplicationSpec(
            application=name, image=IMAGE1, config=fiaas_yml, additional_labels=additional_labels
        )
        return name, metadata, spec

    def _resource_labels(self, param):
        additional_labels = None
        if len(param) == 2:
            fiaas_path, expected = param
        elif len(param) == 3:
            fiaas_path, expected, additional_labels = param
        return fiaas_path, expected, additional_labels

    def _ensure_clean(self, name, expected):
        kinds = self._select_kinds(expected)
        for kind in kinds:
            try:
                kind.delete(name)
            except NotFound:
                pass

    @staticmethod
    def _end_popen(popen):
        popen.terminate()
        time.sleep(1)
        if popen.poll() is None:
            popen.kill()

    @staticmethod
    def _select_kinds(expected):
        if len(list(expected.keys())) > 0:
            return list(expected.keys())
        else:
            return [Service, Deployment, Ingress]

    def run_crd_deploy(self, custom_resource_definition, service_type, service_account=False):
        name, fiaas_application, expected = custom_resource_definition

        # check that k8s objects for name doesn't already exist
        kinds = self._select_kinds(expected)
        for kind in kinds:
            with pytest.raises(NotFound):
                kind.get(name)

        # First deploy
        fiaas_application.save()
        app_uid = fiaas_application.metadata.uid

        # Check that deployment status is RUNNING
        def _assert_status():
            status = FiaasApplicationStatus.get(create_name(name, DEPLOYMENT_ID1))
            status_inline = FiaasApplication.get(name).status.result
            assert status_inline == "RUNNING"
            assert status.result == "RUNNING"
            assert len(status.logs) > 0
            assert any("Saving result RUNNING for default/{}".format(name) in line for line in status.logs)

        wait_until(_assert_status, patience=PATIENCE)

        # Check that annotations and labels are applied to status object
        status_labels = fiaas_application.spec.additional_labels.status
        if status_labels:
            status = FiaasApplicationStatus.get(create_name(name, DEPLOYMENT_ID1))
            label_difference = status_labels.items() - status.metadata.labels.items()
            assert label_difference == set()

        # Check deploy success
        wait_until(
            _deploy_success(name, service_type, IMAGE1, expected, DEPLOYMENT_ID1, app_uid=app_uid), patience=PATIENCE
        )

        if not service_account:
            # Get fiaas_application from server to avoid Conflict error
            fiaas_application = FiaasApplication.get(name)
            # Redeploy, new image, possibly new init-container
            fiaas_application.spec.image = IMAGE2
            fiaas_application.metadata.labels["fiaas/deployment_id"] = DEPLOYMENT_ID2
            strongbox_groups = []
            if "strongbox" in name:
                strongbox_groups = ["foo", "bar"]
                fiaas_application.spec.config["extensions"]["strongbox"]["groups"] = strongbox_groups
            fiaas_application.save()
            app_uid = fiaas_application.metadata.uid
            # Check success
            wait_until(
                _deploy_success(
                    name, service_type, IMAGE2, expected, DEPLOYMENT_ID2, strongbox_groups, app_uid=app_uid
                ),
                patience=PATIENCE,
            )

        # Cleanup
        FiaasApplication.delete(name)

        def cleanup_complete():
            for kind in kinds:
                with pytest.raises(NotFound):
                    kind.get(name)

        wait_until(cleanup_complete, patience=PATIENCE)

    @pytest.mark.usefixtures("fdd", "k8s_client")
    def test_custom_resource_definition_deploy_without_service_account(self, custom_resource_definition, service_type):
        self.run_crd_deploy(custom_resource_definition, service_type)

    @pytest.mark.usefixtures("fdd_service_account", "k8s_client_service_account")
    def test_custom_resource_definition_deploy_with_service_account(self, custom_resource_definition_service_account):
        service_type = "ClusterIP"
        self.run_crd_deploy(custom_resource_definition_service_account, service_type, service_account=True)

    @pytest.mark.usefixtures("fdd", "k8s_client")
    @pytest.mark.parametrize(
        "input, expected",
        [
            (
                "multiple_ingress",
                {
                    "v3-data-examples-multiple-ingress": {
                        Ingress: "e2e_expected/multiple_ingress1.yml",
                        NetworkingV1Ingress: "e2e_expected/multiple_networkingv1-ingress.yml",
                    },
                    "v3-data-examples-multiple-ingress-1": {
                        Ingress: "e2e_expected/multiple_ingress2.yml",
                        NetworkingV1Ingress: "e2e_expected/multiple_networkingv1-ingress2.yml",
                    },
                },
            ),
            (
                "multiple_ingress_default_host",
                {
                    "v3-data-examples-multiple-ingress-default-host": {
                        Ingress: "e2e_expected/multiple_ingress_default_host1.yml",
                        NetworkingV1Ingress: "e2e_expected/multiple_networkingv1-ingress_default_host1.yml",
                    },
                    "v3-data-examples-multiple-ingress-default-host-1": {
                        Ingress: "e2e_expected/multiple_ingress_default_host2.yml",
                        NetworkingV1Ingress: "e2e_expected/multiple_networkingv1-ingress_default_host2.yml",
                    },
                },
            ),
            (
                "tls_issuer_override",
                {
                    "v3-data-examples-tls-issuer-override": {
                        Ingress: "e2e_expected/tls_issuer_override1.yml",
                        NetworkingV1Ingress: "e2e_expected/tls_issuer_networkingv1_override1.yml",
                    },
                    "v3-data-examples-tls-issuer-override-1": {
                        Ingress: "e2e_expected/tls_issuer_override2.yml",
                        NetworkingV1Ingress: "e2e_expected/tls_issuer_networkingv1_override2.yml",
                    },
                },
            ),
        ],
    )
    def test_multiple_ingresses(self, request, input, expected, k8s_version):
        fiaas_path = "v3/data/examples/%s.yml" % input
        fiaas_yml = read_yml(request.fspath.dirpath().join("specs").join(fiaas_path).strpath)

        name = sanitize_resource_name(fiaas_path)

        if use_networkingv1_ingress(k8s_version):
            k8s_ingress = NetworkingV1Ingress
        else:
            k8s_ingress = Ingress
        expected = {
            k: read_yml(request.fspath.dirpath().join(v[k8s_ingress]).strpath) for (k, v) in list(expected.items())
        }

        metadata = ObjectMeta(name=name, namespace="default", labels={"fiaas/deployment_id": DEPLOYMENT_ID1})
        spec = FiaasApplicationSpec(application=name, image=IMAGE1, config=fiaas_yml)
        fiaas_application = FiaasApplication(metadata=metadata, spec=spec)

        fiaas_application.save()
        app_uid = fiaas_application.metadata.uid

        # Check that deployment status is RUNNING
        def _assert_status():
            status = FiaasApplicationStatus.get(create_name(name, DEPLOYMENT_ID1))
            status_inline = FiaasApplication.get(name).status.result
            assert status_inline == "RUNNING"
            assert status.result == "RUNNING"
            assert len(status.logs) > 0
            assert any("Saving result RUNNING for default/{}".format(name) in line for line in status.logs)

        wait_until(_assert_status, patience=PATIENCE)

        def _check_two_ingresses():
            assert k8s_ingress.get(name)
            assert k8s_ingress.get("{}-1".format(name))

            for ingress_name, expected_dict in list(expected.items()):
                actual = k8s_ingress.get(ingress_name)
                assert_k8s_resource_matches(actual, expected_dict, IMAGE1, None, DEPLOYMENT_ID1, None, app_uid)

        wait_until(_check_two_ingresses, patience=PATIENCE)

        # Get fiaas_application from server to avoid Conflict error
        fiaas_application = FiaasApplication.get(name)
        # Remove 2nd ingress to make sure cleanup works
        fiaas_application.spec.config["ingress"].pop()
        if not fiaas_application.spec.config["ingress"]:
            # if the test contains only one ingress,
            # deleting the list will force the creation of the default ingress
            del fiaas_application.spec.config["ingress"]
        fiaas_application.metadata.labels["fiaas/deployment_id"] = DEPLOYMENT_ID2
        fiaas_application.save()

        def _check_one_ingress():
            assert k8s_ingress.get(name)
            with pytest.raises(NotFound):
                k8s_ingress.get("{}-1".format(name))

        wait_until(_check_one_ingress, patience=PATIENCE)

        # Cleanup
        FiaasApplication.delete(name)

        def cleanup_complete():
            for name, _ in list(expected.items()):
                with pytest.raises(NotFound):
                    k8s_ingress.get(name)

        wait_until(cleanup_complete, patience=PATIENCE)


def _deploy_success(name, service_type, image, expected, deployment_id, strongbox_groups=None, app_uid=None):
    def action():
        for kind, expected_dict in list(expected.items()):
            if expected_dict == SHOULD_NOT_EXIST:
                with pytest.raises(NotFound):
                    kind.get(name)
            else:
                actual = kind.get(name)
                assert_k8s_resource_matches(
                    actual, expected_dict, image, service_type, deployment_id, strongbox_groups, app_uid
                )

    return action
