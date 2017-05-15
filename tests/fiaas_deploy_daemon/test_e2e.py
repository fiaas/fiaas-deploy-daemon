#!/usr/bin/env python
# -*- coding: utf-8

import contextlib
import os
import os.path
import socket
import subprocess
import time

import pytest
import re
import requests
import yaml
from monotonic import monotonic as time_monotonic
from k8s import config
from k8s.client import NotFound, Client
from k8s.models.deployment import Deployment
from k8s.models.ingress import Ingress
from k8s.models.service import Service
from k8s.models.common import ObjectMeta
from fiaas_deploy_daemon.tpr.paasbetaapplication import (PaasbetaApplication, PaasbetaApplicationSpec,
                                                         PaasApplicationConfig)

IMAGE1 = "finntech/application-name:123"
IMAGE2 = "finntech/application-name:321"


def _has_utilities():
    try:
        subprocess.check_call(["minikube", "version"])
        subprocess.check_call(["kubectl", "version", "--client"])
    except (subprocess.CalledProcessError, OSError):
        return False
    return True


def _is_macos():
    return os.uname()[0] == 'Darwin'


def _has_xhyve_driver():
    path = os.environ['PATH']
    return any(os.access(os.path.join(p, 'docker-machine-driver-xhyve'), os.X_OK) for p in path.split(os.pathsep))


@pytest.fixture(scope="session", params=("ClusterIP", "NodePort"))
def service_type(request):
    return request.param


@pytest.mark.skipif(not _has_utilities(), reason="E2E test requires minikube and kubectl installed on the PATH")
@pytest.mark.integration_test
class TestE2E(object):
    @pytest.fixture(scope="module")
    def kubernetes(self, service_type):
        subprocess.call(["minikube", "delete"])
        self._start_minikube()
        subprocess.check_call(["kubectl", "config", "use-context", "minikube"])
        output = subprocess.check_output(["kubectl", "config", "view", "--minify", "-oyaml"])
        kubectl_config = yaml.safe_load(output)
        yield {
            "server": kubectl_config[u"clusters"][0][u"cluster"][u"server"],
            "client-cert": kubectl_config[u"users"][0][u"user"][u"client-certificate"],
            "client-key": kubectl_config[u"users"][0][u"user"][u"client-key"]
        }
        subprocess.check_call(["minikube", "delete"])

    @staticmethod
    def _start_minikube():
        running = False
        start = time.time()
        while not running and time.time() < (start + 60):
            extra_args = ["--vm-driver", "xhyve"] if _is_macos() and _has_xhyve_driver() else []
            subprocess.call(["minikube", "start"] + extra_args)
            time.sleep(5)
            running = (subprocess.call(["kubectl", "cluster-info"]) == 0)
        if not running:
            raise RuntimeError("Minikube won't start")

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
                                "--client-cert", kubernetes["client-cert"],
                                "--client-key", kubernetes["client-key"],
                                "--service-type", service_type,
                                "--ingress-suffix", "svc.test.example.com",
                                "--environment", "test"
                                ])
        time.sleep(1)
        yield "http://localhost:{}/fiaas".format(port)
        self._end_popen(fdd)

    @pytest.fixture(scope="module")
    def fdd_tpr_support_enabled(self, kubernetes, service_type):
        port = self._get_open_port()
        fdd = subprocess.Popen(["fiaas-deploy-daemon",
                                "--debug",
                                "--port", str(port),
                                "--api-server", kubernetes["server"],
                                "--client-cert", kubernetes["client-cert"],
                                "--client-key", kubernetes["client-key"],
                                "--service-type", service_type,
                                "--ingress-suffix", "svc.test.example.com",
                                "--environment", "test",
                                "--enable-tpr-support"
                                ])
        time.sleep(1)
        yield "http://localhost:{}/fiaas".format(port)
        self._end_popen(fdd)

    @pytest.fixture(params=(
            "data/v1minimal.yml",
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
        time.sleep(1)
        yield (self._sanitize(request.param), "http://localhost:{}/{}".format(port, request.param))
        self._end_popen(httpd)

    @pytest.fixture(params=(
            "data/v1minimal.yml",
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
        metadata = ObjectMeta(name=name, namespace="default")
        spec = PaasbetaApplicationSpec(application=name, image=IMAGE1,
                                       config=PaasApplicationConfig.from_dict(fiaas_yml))
        return (name, PaasbetaApplication(metadata=metadata, spec=spec))

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

    @pytest.fixture(autouse=True)
    def third_party_resource_type(self, request, kubernetes):
        tpr_path = os.path.abspath(os.path.join(request.fspath.dirpath().strpath, "..", "..", "tpr",
                                                "PaasbetaApplication.yaml"))
        kubectl_replace = subprocess.Popen(["kubectl", "replace", "--force=true", "-f", tpr_path])
        status = kubectl_replace.wait()
        timeout_seconds = 30
        timeout = time_monotonic() + timeout_seconds
        while time_monotonic() < timeout:  # wait for the resource to be usable in the cluster
            kubectl_get = subprocess.Popen(["kubectl", "get", "paasbetaapplications"])
            status = kubectl_get.wait()
            if status == 0:
                return True
            else:
                time.sleep(5)
        pytest.fail("paasbetaapplication ThirdPartyResource was not available after {}s".format(
            timeout=timeout_seconds))

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
            "tags": ["testtags"]
        }
        resp = requests.post(fdd, data)
        resp.raise_for_status()

        # Check deploy success
        time.sleep(5)
        for kind in kinds:
            assert kind.get(name)
        dep = Deployment.get(name)
        assert dep.spec.template.spec.containers[0].image == IMAGE1
        svc = Service.get(name)
        assert svc.spec.type == service_type

        # Redeploy, new image
        data["image"] = IMAGE2
        resp = requests.post(fdd, data)
        resp.raise_for_status()

        # Check success
        time.sleep(5)
        for kind in kinds:
            assert kind.get(name)
        dep = Deployment.get(name)
        assert dep.spec.template.spec.containers[0].image == IMAGE2

        # Cleanup
        for kind in kinds:
            kind.delete(name)

    def test_third_party_resource_deploy(self, third_party_resource_type, fdd_tpr_support_enabled,
                                         third_party_resource, service_type):
        name, paasbetaapplication = third_party_resource

        # check that k8s objects for name doesn't already exist
        kinds = self._select_kinds(name)
        for kind in kinds:
            with pytest.raises(NotFound):
                kind.get(name)

        # First deploy
        paasbetaapplication.save()

        # Check deploy success
        time.sleep(5)
        for kind in kinds:
            assert kind.get(name)
        dep = Deployment.get(name)
        assert dep.spec.template.spec.containers[0].image == IMAGE1
        svc = Service.get(name)
        assert svc.spec.type == service_type

        # Redeploy, new image
        paasbetaapplication_new = PaasbetaApplication.get(name)
        paasbetaapplication_new.spec.image = IMAGE2
        paasbetaapplication_new.save()

        # Check success
        time.sleep(5)
        for kind in kinds:
            assert kind.get(name)
        dep = Deployment.get(name)
        assert dep.spec.template.spec.containers[0].image == IMAGE2

        # Cleanup
        for kind in kinds:
            kind.delete(name)
