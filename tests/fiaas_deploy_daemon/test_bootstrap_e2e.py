#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import subprocess
import sys

import pytest

from k8s import config
from k8s.client import Client
from minikube import MinikubeError
from fiaas_deploy_daemon.tools import merge_dicts
from fiaas_deploy_daemon.tpr.watcher import TprWatcher
from fiaas_deploy_daemon.crd.watcher import CrdWatcher

from utils import wait_until, tpr_available, crd_available, tpr_supported, crd_supported

# set up minikube
# - wait for minikube being available
# create TPR and/or CRD types
# - wait for type being available
# create Paasbeta/Fiaas application resource; keep total number of cases low
# - check valid config
# - check deploy to multiple namespaces
# - check only deploy with correct label
# - invalid config should cause bad exit status
# run fiaas-deploy-daemon-bootstrap
# - wait for execution to complete, check for exit status
# wait for/assert results

# dependencies/shared code
# - minikube installer
#   - can be shared and kept as per-session fixture = faster
# - wait_for
# - crd/tpr available
# plog?

# modify FixtureScheduling to run tests in parallell in the same way as test_e2e

PATIENCE = 30
TIMEOUT = 5


@pytest.mark.integration_test
class TestBootstrapE2E(object):

    @pytest.fixture(scope="module")
    def kubernetes(self, minikube_installer, k8s_version):
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
        args = ["fiaas-deploy-daemon-bootstrap",
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

    def test_bootstrap(self, kubernetes, k8s_version):

        if tpr_supported(k8s_version):
            TprWatcher.create_third_party_resource()
            wait_until(tpr_available(kubernetes, timeout=TIMEOUT), "TPR available", RuntimeError, patience=PATIENCE)
        if crd_supported(k8s_version):
            CrdWatcher.create_custom_resource_definitions()
            wait_until(crd_available(kubernetes, timeout=TIMEOUT), "CRD available", RuntimeError, patience=PATIENCE)

        # create test resources

        self.run_bootstrap(kubernetes, k8s_version)

        # assert
