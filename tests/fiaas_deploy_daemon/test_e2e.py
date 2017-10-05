#!/usr/bin/env python
# -*- coding: utf-8

import contextlib
import socket
import subprocess
import sys
import time
import traceback
from urlparse import urljoin

import pytest
import re
import requests
import yaml
from k8s import config
from k8s.client import NotFound, Client
from k8s.models.common import ObjectMeta
from k8s.models.deployment import Deployment
from k8s.models.ingress import Ingress
from k8s.models.service import Service
from monotonic import monotonic as time_monotonic

from fiaas_deploy_daemon.tpr.status import create_name
from fiaas_deploy_daemon.tpr.types import (PaasbetaApplication, PaasbetaApplicationSpec,
                                           PaasApplicationConfig, PaasbetaStatus)
from minikube import MinikubeInstaller, MinikubeError

IMAGE1 = u"finntech/application-name:123"
IMAGE2 = u"finntech/application-name:321"
DEPLOYMENT_ID1 = u"deployment_id_1"
DEPLOYMENT_ID2 = u"deployment_id_2"
PATIENCE = 300


def _wait_until(action, description=None, exception_class=AssertionError, patience=PATIENCE):
    """Attempt to call 'action' every 2 seconds, until it completes without exception or patience runs out"""
    __tracebackhide__ = True

    start = time_monotonic()
    cause = []
    if not description:
        description = action.__doc__ or action.__name__
    message = ["Gave up waiting for {} after {} seconds".format(description, patience)]
    while time_monotonic() < (start + patience):
        try:
            action()
            return
        except BaseException:
            cause = traceback.format_exception(*sys.exc_info())
        time.sleep(2)
    if cause:
        message.append("\nThe last exception was:\n")
        message.extend(cause)
    raise exception_class("".join(message))


def _wait_for_tpr_available(kubernetes):
    start = time_monotonic()
    app_url = urljoin(kubernetes["server"], PaasbetaApplication._meta.watch_list_url)
    status_url = urljoin(kubernetes["server"], PaasbetaStatus._meta.url_template.format(namespace="default", name=""))
    session = requests.Session()
    session.verify = kubernetes["api-cert"]
    session.cert = (kubernetes["client-cert"], kubernetes["client-key"])
    while time_monotonic() < (start + PATIENCE):
        for url in (app_url, status_url):
            resp = session.get(url)
            if resp.status_code >= 400:
                time.sleep(5)
                continue
        return
    raise RuntimeError("The ThirdPartyResources are not available after {} seconds".format(PATIENCE))


@pytest.fixture(scope="session")
def minikube_installer():
    try:
        mki = MinikubeInstaller()
        mki.install()
        yield mki
        mki.cleanup()
    except MinikubeError as e:
        msg = "Unable to install minikube: %s"
        pytest.skip(msg % str(e))


@pytest.fixture(scope="session", params=("ClusterIP", "NodePort"))
def service_type(request):
    return request.param


@pytest.mark.integration_test
class TestE2E(object):
    @pytest.fixture(scope="module")
    def kubernetes(self, minikube_installer, service_type):
        try:
            minikube = minikube_installer.new(profile=service_type, k8s_version='v1.6.4')
            minikube.delete()
            minikube.start()
            yield {
                "server": minikube.server,
                "client-cert": minikube.client_cert,
                "client-key": minikube.client_key,
                "api-cert": minikube.api_cert
            }
            minikube.delete()
        except MinikubeError as e:
            msg = "Unable to run minikube: %s"
            pytest.skip(msg % str(e))

    @pytest.fixture(autouse=True)
    def k8s_client(self, kubernetes):
        Client.clear_session()
        config.api_server = kubernetes["server"]
        config.debug = True
        config.verify_ssl = False
        config.cert = (kubernetes["client-cert"], kubernetes["client-key"])

    @pytest.fixture(scope="module")
    def fdd(self, kubernetes, service_type):
        port = self._get_open_port()
        fdd = subprocess.Popen(["fiaas-deploy-daemon",
                                "--debug",
                                "--port", str(port),
                                "--api-server", kubernetes["server"],
                                "--api-cert", kubernetes["api-cert"],
                                "--client-cert", kubernetes["client-cert"],
                                "--client-key", kubernetes["client-key"],
                                "--service-type", service_type,
                                "--ingress-suffix", "svc.test.example.com",
                                "--environment", "test"
                                ])

        def ready():
            resp = requests.get("http://localhost:{}/healthz".format(port))
            resp.raise_for_status()

        _wait_until(ready, "web-interface healthy", RuntimeError)
        yield "http://localhost:{}/fiaas".format(port)
        self._end_popen(fdd)

    @pytest.fixture(scope="module")
    def fdd_tpr_support_enabled(self, kubernetes, service_type):
        port = self._get_open_port()
        fdd = subprocess.Popen(["fiaas-deploy-daemon",
                                "--debug",
                                "--port", str(port),
                                "--api-server", kubernetes["server"],
                                "--api-cert", kubernetes["api-cert"],
                                "--client-cert", kubernetes["client-cert"],
                                "--client-key", kubernetes["client-key"],
                                "--service-type", service_type,
                                "--ingress-suffix", "svc.test.example.com",
                                "--environment", "test",
                                "--enable-tpr-support"
                                ])
        _wait_for_tpr_available(kubernetes)
        yield "http://localhost:{}/fiaas".format(port)
        self._end_popen(fdd)

    @pytest.fixture(params=(
            "data/v2minimal.yml",
            "v2/data/host.yml",
            "v2/data/exec_config.yml",
            "v2/data/config_as_env.yml",
            "v2/data/config_as_volume.yml"
    ))
    def fiaas_yml(self, request):
        port = self._get_open_port()
        data_dir = request.fspath.dirpath().join("specs")
        httpd = subprocess.Popen(["python", "-m", "SimpleHTTPServer", str(port)],
                                 cwd=data_dir.strpath)
        fiaas_yml_url = "http://localhost:{}/{}".format(port, request.param)

        def ready():
            resp = requests.get(fiaas_yml_url)
            resp.raise_for_status()

        _wait_until(ready, "web-interface healthy", RuntimeError)
        yield (self._sanitize(request.param), fiaas_yml_url)
        self._end_popen(httpd)

    @pytest.fixture(params=(
            "data/v2minimal.yml",
            "v2/data/host.yml",
            "v2/data/exec_config.yml",
            "v2/data/config_as_env.yml",
            "v2/data/config_as_volume.yml"
    ))
    def third_party_resource(self, request):
        fiaas_yml_path = request.fspath.dirpath().join("specs").join(request.param).strpath
        with open(fiaas_yml_path, 'r') as fobj:
            fiaas_yml = yaml.safe_load(fobj)

        name = self._sanitize(request.param)
        metadata = ObjectMeta(name=name, namespace="default", labels={"fiaas/deployment_id": DEPLOYMENT_ID1})
        spec = PaasbetaApplicationSpec(application=name, image=IMAGE1,
                                       config=PaasApplicationConfig.from_dict(fiaas_yml))
        return name, PaasbetaApplication(metadata=metadata, spec=spec)

    @staticmethod
    def _sanitize(param):
        """must match the regex [a-z]([-a-z0-9]*[a-z0-9])?"""
        return re.sub("[^-a-z0-9]", "-", param.replace(".yml", ""))

    @staticmethod
    def _end_popen(popen):
        popen.terminate()
        time.sleep(1)
        if popen.poll() is None:
            popen.kill()

    @staticmethod
    def _get_open_port():
        with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.bind(("", 0))
            return s.getsockname()[1]

    @staticmethod
    def _select_kinds(name):
        kinds = [Service, Deployment]
        if "host" in name:
            kinds.append(Ingress)
        return kinds

    def test_post_to_web(self, fdd, fiaas_yml, service_type):
        name, url = fiaas_yml
        kinds = self._select_kinds(name)
        for kind in kinds:
            with pytest.raises(NotFound):
                kind.get(name)

        # First deploy
        data = {
            "name": name,
            "image": IMAGE1,
            "fiaas": url,
            "teams": ["testteam"],
            "tags": ["testtags"],
            "deployment_id": DEPLOYMENT_ID1
        }
        resp = requests.post(fdd, data)
        resp.raise_for_status()

        # Check deploy success
        _wait_until(_deploy_success(name, kinds, service_type, IMAGE1))

        # Redeploy, new image
        data["image"] = IMAGE2
        resp = requests.post(fdd, data)
        resp.raise_for_status()

        # Check redeploy success
        _wait_until(_deploy_success(name, kinds, service_type, IMAGE2))

        # Cleanup
        for kind in kinds:
            kind.delete(name)

    def test_third_party_resource_deploy(self, fdd_tpr_support_enabled,
                                         third_party_resource, service_type):
        name, paasbetaapplication = third_party_resource

        # check that k8s objects for name doesn't already exist
        kinds = self._select_kinds(name)
        for kind in kinds:
            with pytest.raises(NotFound):
                kind.get(name)

        # First deploy
        paasbetaapplication.save()

        # Check that deployment status is RUNNING
        _wait_until(lambda: _assert_status(name, DEPLOYMENT_ID1, u"RUNNING"))

        # Check deploy success
        _wait_until(_deploy_success(name, kinds, service_type, IMAGE1))

        # Redeploy, new image
        paasbetaapplication.spec.image = IMAGE2
        paasbetaapplication.metadata.labels["fiaas/deployment_id"] = DEPLOYMENT_ID2
        paasbetaapplication.save()

        # Check success
        _wait_until(_deploy_success(name, kinds, service_type, IMAGE2))

        # Cleanup
        PaasbetaApplication.delete(name)

        def cleanup_complete():
            for kind in kinds:
                with pytest.raises(NotFound):
                    kind.get(name)
        _wait_until(cleanup_complete)


def _assert_status(name, deployment_id, result):
    status = PaasbetaStatus.get(create_name(name, deployment_id))
    assert status.result == result


def _deploy_success(name, kinds, service_type, image):
    def action():
        for kind in kinds:
            assert kind.get(name)
        dep = Deployment.get(name)
        assert dep.spec.template.spec.containers[0].image == image
        svc = Service.get(name)
        assert svc.spec.type == service_type
    return action
