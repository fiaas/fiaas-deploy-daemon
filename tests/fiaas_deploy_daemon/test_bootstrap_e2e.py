#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
from k8s.models.service import Service
from minikube import MinikubeError
from fiaas_deploy_daemon.tools import merge_dicts
from fiaas_deploy_daemon.tpr.watcher import TprWatcher
from fiaas_deploy_daemon.crd.watcher import CrdWatcher
from fiaas_deploy_daemon.crd.types import FiaasApplication, FiaasApplicationSpec
from fiaas_deploy_daemon.tpr.types import PaasbetaApplication, PaasbetaApplicationSpec

from utils import wait_until, tpr_available, crd_available, tpr_supported, crd_supported, skip_if_tpr_not_supported, \
    skip_if_crd_not_supported, read_yml, sanitize_resource_name, assert_k8s_resource_matches


PATIENCE = 30
TIMEOUT = 5
IMAGE = "nginx:1.13.9-alpine"  # we need an actual functional image with a service in it, and this is as good as any
DEPLOYMENT_ID = "1"
SHOULD_NOT_EXIST = object()  # Mapped to Kinds that should not exist in a test case
# Test case format: (path_to_fiaas_yml, namespace, labels, {Kind: path/to/expected_k8s.yml or SHOULD_NOT_EXIST})
TEST_CASES = (
    ("specs/v2/data/examples/v2bootstrap.yml", "default", {"fiaas/bootstrap": "true"}, {
        Service: "bootstrap_e2e_expected/v2bootstrap-service.yml",
        Deployment: "bootstrap_e2e_expected/v2bootstrap-deployment.yml",
        Ingress: "bootstrap_e2e_expected/v2bootstrap-ingress.yml",
        HorizontalPodAutoscaler: SHOULD_NOT_EXIST,
    }),
    ("specs/v2/data/examples/v2bootstrap.yml", "kube-system", {"fiaas/bootstrap": "false"}, {
        Service: SHOULD_NOT_EXIST,
        Deployment: SHOULD_NOT_EXIST,
        Ingress: SHOULD_NOT_EXIST,
        HorizontalPodAutoscaler: SHOULD_NOT_EXIST,
    }),
    ("specs/v3/data/examples/v3bootstrap.yml", "kube-system", {"fiaas/bootstrap": "true"}, {
        Service: "bootstrap_e2e_expected/v3bootstrap-service.yml",
        Deployment: "bootstrap_e2e_expected/v3bootstrap-deployment.yml",
        Ingress: "bootstrap_e2e_expected/v3bootstrap-ingress.yml",
        HorizontalPodAutoscaler: "bootstrap_e2e_expected/v3bootstrap-hpa.yml",
    }),
    ("specs/v3/data/examples/v3bootstrap.yml", "default", {}, {
        Service: SHOULD_NOT_EXIST,
        Deployment: SHOULD_NOT_EXIST,
        Ingress: SHOULD_NOT_EXIST,
        HorizontalPodAutoscaler: SHOULD_NOT_EXIST,
    }),
)


def file_relative_path(relative_path):
    return os.path.abspath(os.path.join(os.path.dirname(__file__), relative_path))


@pytest.mark.integration_test
class TestBootstrapE2E(object):

    @pytest.fixture(scope="module")
    def kubernetes(self, request, minikube_installer, k8s_version):
        try:
            minikube = minikube_installer.new(profile="bootstrap", k8s_version=k8s_version)
            try:
                minikube.start()
                yield {
                    "server": minikube.server,
                    "client-cert": minikube.client_cert,
                    "client-key": minikube.client_key,
                    "api-cert": minikube.api_cert
                }
            finally:
                minikube.delete()
        except MinikubeError as e:
            msg = "Unable to run minikube: %s"
            pytest.fail(msg % str(e))

    @pytest.fixture(autouse=True)
    def k8s_client(self, kubernetes):
        Client.clear_session()
        config.api_server = kubernetes["server"]
        config.debug = True
        config.verify_ssl = False
        config.cert = (kubernetes["client-cert"], kubernetes["client-key"])

    def run_bootstrap(self, kubernetes, k8s_version, patience=PATIENCE):
        args = [
            "fiaas-deploy-daemon-bootstrap",
            "--debug",
            "--api-server", kubernetes["server"],
            "--api-cert", kubernetes["api-cert"],
            "--client-cert", kubernetes["client-cert"],
            "--client-key", kubernetes["client-key"],
        ]
        if tpr_supported(k8s_version):
            args.append("--enable-tpr-support")
        if crd_supported(k8s_version):
            args.append("--enable-crd-support")

        bootstrap = subprocess.Popen(args, stdout=sys.stderr, env=merge_dicts(os.environ, {"NAMESPACE": "default"}))
        return bootstrap.wait()

    def custom_resource_definition_test_case(self, fiaas_path, namespace, labels, expected):
        fiaas_yml = read_yml(file_relative_path(fiaas_path))
        expected = {kind: read_yml(file_relative_path(path)) for kind, path in expected.items()
                    if path is not SHOULD_NOT_EXIST}

        name = sanitize_resource_name(fiaas_path)

        metadata = ObjectMeta(name=name, namespace=namespace,
                              labels=merge_dicts(labels, {"fiaas/deployment_id": DEPLOYMENT_ID}))
        spec = FiaasApplicationSpec(application=name, image=IMAGE, config=fiaas_yml)
        return name, FiaasApplication(metadata=metadata, spec=spec), expected

    def third_party_resource_test_case(self, fiaas_path, namespace, labels, expected):
        fiaas_yml = read_yml(file_relative_path(fiaas_path))
        expected = {kind: read_yml(file_relative_path(path)) for kind, path in expected.items()
                    if path is not SHOULD_NOT_EXIST}

        name = sanitize_resource_name(fiaas_path)

        metadata = ObjectMeta(name=name, namespace=namespace,
                              labels=merge_dicts(labels, {"fiaas/deployment_id": DEPLOYMENT_ID}))
        spec = PaasbetaApplicationSpec(application=name, image=IMAGE, config=fiaas_yml)
        return name, PaasbetaApplication(metadata=metadata, spec=spec), expected

    def test_bootstrap_crd(self, kubernetes, k8s_version):
        skip_if_crd_not_supported(k8s_version)

        CrdWatcher.create_custom_resource_definitions()
        wait_until(crd_available(kubernetes, timeout=TIMEOUT), "CRD available", RuntimeError, patience=PATIENCE)

        def prepare_test_case(test_case):
            name, fiaas_application, expected = self.custom_resource_definition_test_case(*test_case)

            # check that k8s objects for name doesn't already exist
            for kind in expected.keys():
                with pytest.raises(NotFound):
                    kind.get(name)

            fiaas_application.save()

            return name, fiaas_application.metadata.namespace, expected

        expectations = [prepare_test_case(test_case) for test_case in TEST_CASES]

        exit_code = self.run_bootstrap(kubernetes, k8s_version)
        assert exit_code == 0

        def success():
            all(deploy_successful(name, namespace, expected) for name, namespace, expected in expectations)

        wait_until(success, "TPR bootstrapping was successful", patience=PATIENCE)

        for name, namespace, expected in expectations:
            for kind in expected.keys():
                try:
                    kind.delete(name, namespace=namespace)
                except NotFound:
                    pass  # already missing

    def test_bootstrap_tpr(self, kubernetes, k8s_version):
        skip_if_tpr_not_supported(k8s_version)
        TprWatcher.create_third_party_resource()
        wait_until(tpr_available(kubernetes, timeout=TIMEOUT), "TPR available", RuntimeError, patience=PATIENCE)

        def prepare_test_case(test_case):
            name, paasbeta_application, expected = self.third_party_resource_test_case(*test_case)

            # check that k8s objects for name doesn't already exist
            for kind in expected.keys():
                with pytest.raises(NotFound):
                    kind.get(name)

            paasbeta_application.save()

            return name, paasbeta_application.metadata.namespace, expected

        expectations = [prepare_test_case(test_case) for test_case in TEST_CASES]

        exit_code = self.run_bootstrap(kubernetes, k8s_version)
        assert exit_code == 0

        def success():
            all(deploy_successful(name, namespace, expected) for name, namespace, expected in expectations)

        wait_until(success, "TPR bootstrapping was successful", patience=PATIENCE)

        for name, namespace, expected in expectations:
            for kind in expected.keys():
                try:
                    kind.delete(name, namespace=namespace)
                except NotFound:
                    pass  # already missing


def deploy_successful(name, namespace, expected):
    for kind, expected_result in expected.items():
        if expected_result == SHOULD_NOT_EXIST:
            with pytest.raises(NotFound):
                kind.get(name, namespace=namespace)
        else:
            actual = kind.get(name, namespace=namespace)
            assert_k8s_resource_matches(actual, expected_result, IMAGE, "ClusterIP", DEPLOYMENT_ID, [])
