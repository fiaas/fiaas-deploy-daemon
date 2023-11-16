#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
import os.path
import subprocess
import sys

import pytest
from k8s import config
from k8s.client import Client, NotFound
from k8s.models.autoscaler import HorizontalPodAutoscaler
from k8s.models.common import ObjectMeta
from k8s.models.deployment import Deployment
from k8s.models.ingress import Ingress
from k8s.models.networking_v1_ingress import Ingress as NetworkingV1Ingress
from k8s.models.service import Service

from fiaas_deploy_daemon.crd.types import FiaasApplication, FiaasApplicationSpec
from fiaas_deploy_daemon.crd.crd_resources_syncer_apiextensionsv1 import CrdResourcesSyncerApiextensionsV1
from fiaas_deploy_daemon.crd.crd_resources_syncer_apiextensionsv1beta1 import CrdResourcesSyncerApiextensionsV1Beta1
from fiaas_deploy_daemon.tools import merge_dicts
from utils import (
    wait_until,
    crd_available,
    read_yml,
    sanitize_resource_name,
    assert_k8s_resource_matches,
    get_unbound_port,
    KindWrapper,
    uuid,
    use_apiextensionsv1_crd,
    use_networkingv1_ingress,
)

PATIENCE = 30
TIMEOUT = 5
IMAGE = "nginx:1.13.9-alpine"  # we need an actual functional image with a service in it, and this is as good as any
DEPLOYMENT_ID = "1"
SHOULD_NOT_EXIST = object()  # Mapped to Kinds that should not exist in a test case
# Test case format: (path_to_fiaas_yml, namespace, labels, {Kind: path/to/expected_k8s.yml or SHOULD_NOT_EXIST})
TEST_CASES = (
    (
        "specs/v2/data/examples/v2bootstrap.yml",
        "default",
        {"fiaas/bootstrap": "true"},
        {
            Service: "bootstrap_e2e_expected/v2bootstrap-service.yml",
            Deployment: "bootstrap_e2e_expected/v2bootstrap-deployment.yml",
            Ingress: "bootstrap_e2e_expected/v2bootstrap-ingress.yml",
            NetworkingV1Ingress: "bootstrap_e2e_expected/v2bootstrap-networkingv1-ingress.yml",
            HorizontalPodAutoscaler: SHOULD_NOT_EXIST,
        },
    ),
    (
        "specs/v2/data/examples/v2bootstrap.yml",
        "kube-system",
        {"fiaas/bootstrap": "false"},
        {
            Service: SHOULD_NOT_EXIST,
            Deployment: SHOULD_NOT_EXIST,
            Ingress: SHOULD_NOT_EXIST,
            NetworkingV1Ingress: SHOULD_NOT_EXIST,
            HorizontalPodAutoscaler: SHOULD_NOT_EXIST,
        },
    ),
    (
        "specs/v3/data/examples/v3bootstrap.yml",
        "default",
        {"fiaas/bootstrap": "true"},
        {
            Service: "bootstrap_e2e_expected/v3bootstrap-service.yml",
            Deployment: "bootstrap_e2e_expected/v3bootstrap-deployment.yml",
            Ingress: "bootstrap_e2e_expected/v3bootstrap-ingress.yml",
            NetworkingV1Ingress: "bootstrap_e2e_expected/v3bootstrap-networkingv1-ingress.yml",
            HorizontalPodAutoscaler: "bootstrap_e2e_expected/v3bootstrap-hpa.yml",
        },
    ),
    (
        "specs/v3/data/examples/full.yml",
        "default",
        {},
        {
            Service: SHOULD_NOT_EXIST,
            Deployment: SHOULD_NOT_EXIST,
            Ingress: SHOULD_NOT_EXIST,
            NetworkingV1Ingress: SHOULD_NOT_EXIST,
            HorizontalPodAutoscaler: SHOULD_NOT_EXIST,
        },
    ),
    (
        "specs/v3/data/examples/v3minimal.yml",
        "kube-system",
        {"fiaas/bootstrap": "true"},
        {
            Service: SHOULD_NOT_EXIST,
            Deployment: SHOULD_NOT_EXIST,
            Ingress: SHOULD_NOT_EXIST,
            NetworkingV1Ingress: SHOULD_NOT_EXIST,
            HorizontalPodAutoscaler: SHOULD_NOT_EXIST,
        },
    ),
)


def file_relative_path(relative_path):
    return os.path.abspath(os.path.join(os.path.dirname(__file__), relative_path))


@pytest.mark.integration_test
class TestBootstrapE2E(object):
    @pytest.fixture(scope="module")
    def kubernetes(self, k8s_version):
        try:
            name = "kind-bootstrap-{}-{}".format(k8s_version, uuid())
            kind = KindWrapper(k8s_version, name)
            try:
                yield kind.start()
            finally:
                kind.delete()
        except Exception as e:
            msg = "Unable to run kind: %s"
            pytest.fail(msg % str(e))

    @pytest.fixture(autouse=True)
    def k8s_client(self, kubernetes):
        Client.clear_session()
        config.api_server = kubernetes["host-to-container-server"]
        config.debug = True
        config.verify_ssl = False
        config.cert = (kubernetes["client-cert"], kubernetes["client-key"])

    def run_bootstrap(self, request, kubernetes, k8s_version, use_docker_for_e2e):
        cert_path = os.path.dirname(kubernetes["api-cert"])
        docker_args = use_docker_for_e2e(
            request,
            cert_path,
            "bootstrap",
            k8s_version,
            get_unbound_port(),
            kubernetes["container-to-container-server-ip"],
        )
        server = kubernetes["container-to-container-server"] if docker_args else kubernetes["host-to-container-server"]
        args = [
            "fiaas-deploy-daemon-bootstrap",
            "--debug",
            "--api-server",
            server,
            "--api-cert",
            kubernetes["api-cert"],
            "--client-cert",
            kubernetes["client-cert"],
            "--client-key",
            kubernetes["client-key"],
            "--enable-crd-support",
        ]
        if use_apiextensionsv1_crd(k8s_version):
            args.append("--use-apiextensionsv1-crd")
            args.append("--include-status-in-app")
        if use_networkingv1_ingress(k8s_version):
            args.append("--use-networkingv1-ingress")

        args = docker_args + args
        bootstrap = subprocess.Popen(args, stdout=sys.stderr, env=merge_dicts(os.environ, {"NAMESPACE": "default"}))
        return bootstrap.wait()

    def custom_resource_definition_test_case(self, fiaas_path, namespace, labels, expected, k8s_version=None):
        fiaas_yml = read_yml(file_relative_path(fiaas_path))

        if use_networkingv1_ingress(k8s_version) and expected.get(Ingress):
            del expected[Ingress]
        elif expected.get(NetworkingV1Ingress):
            del expected[NetworkingV1Ingress]
        expected = {kind: read_yml_if_exists(path) for kind, path in list(expected.items())}

        name = sanitize_resource_name(fiaas_path)

        metadata = ObjectMeta(
            name=name, namespace=namespace, labels=merge_dicts(labels, {"fiaas/deployment_id": DEPLOYMENT_ID})
        )
        spec = FiaasApplicationSpec(application=name, image=IMAGE, config=fiaas_yml)
        return name, FiaasApplication(metadata=metadata, spec=spec), expected

    def test_bootstrap_crd(self, request, kubernetes, k8s_version, use_docker_for_e2e):
        if use_apiextensionsv1_crd(k8s_version):
            CrdResourcesSyncerApiextensionsV1.update_crd_resources()
        else:
            CrdResourcesSyncerApiextensionsV1Beta1.update_crd_resources()
        wait_until(crd_available(kubernetes), "CRD resources was created", patience=PATIENCE)

        def prepare_test_case(test_case):
            name, fiaas_application, expected = self.custom_resource_definition_test_case(
                *test_case, k8s_version=k8s_version
            )

            ensure_resources_not_exists(name, expected, fiaas_application.metadata.namespace)

            fiaas_application.save()

            return name, fiaas_application.metadata.namespace, fiaas_application.metadata.uid, expected

        expectations = [prepare_test_case(test_case) for test_case in TEST_CASES]

        exit_code = self.run_bootstrap(request, kubernetes, k8s_version, use_docker_for_e2e)
        assert exit_code == 0

        def success():
            all(
                deploy_successful(name, namespace, app_uid, expected)
                for name, namespace, app_uid, expected in expectations
            )

        wait_until(success, "CRD bootstrapping was successful", patience=PATIENCE)

        for name, namespace, app_uid, expected in expectations:
            for kind in list(expected.keys()):
                try:
                    kind.delete(name, namespace=namespace)
                except NotFound:
                    pass  # already missing


def ensure_resources_not_exists(name, expected, namespace):
    for kind in list(expected.keys()):
        with pytest.raises(NotFound):
            kind.get(name, namespace=namespace)


def deploy_successful(name, namespace, app_uid, expected):
    for kind, expected_result in list(expected.items()):
        if expected_result == SHOULD_NOT_EXIST:
            with pytest.raises(NotFound):
                kind.get(name, namespace=namespace)
        else:
            actual = kind.get(name, namespace=namespace)
            assert_k8s_resource_matches(actual, expected_result, IMAGE, "ClusterIP", DEPLOYMENT_ID, [], app_uid)


def read_yml_if_exists(path):
    if path == SHOULD_NOT_EXIST:
        return path
    else:
        return read_yml(file_relative_path(path))
