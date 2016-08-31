#!/usr/bin/env python
# -*- coding: utf-8

import contextlib
import socket
import subprocess
import time

import pytest
import requests
import yaml
from k8s import config
from k8s.models.deployment import Deployment
from k8s.models.ingress import Ingress
from k8s.models.service import Service

NAME = "application-name"
IMAGE = "finntech/application-name:123"


def _has_minikube():
    try:
        subprocess.check_call(["minikube", "version"])
    except (subprocess.CalledProcessError, OSError):
        return False
    return True


@pytest.mark.skipif(not _has_minikube(), reason="E2E test requires minikube installed on the PATH")
@pytest.mark.integration_test
class TestE2E(object):
    @pytest.fixture
    def kubernetes(self):
        subprocess.call(["minikube", "delete"])
        subprocess.check_call(["minikube", "start", "--kubernetes-version=1.3.4"])
        subprocess.check_call(["kubectl", "config", "use-context", "minikube"])
        output = subprocess.check_output(["kubectl", "config", "view", "--minify", "-oyaml"])
        kubectl_config = yaml.safe_load(output)
        yield {
            "server": kubectl_config[u"clusters"][0][u"cluster"][u"server"],
            "client-cert": kubectl_config[u"users"][0][u"user"][u"client-certificate"],
            "client-key": kubectl_config[u"users"][0][u"user"][u"client-key"]
        }
        subprocess.check_call(["minikube", "delete"])

    @pytest.fixture(autouse=True)
    def k8s_client(self, kubernetes):
        config.api_server = kubernetes["server"]
        config.debug = True
        config.verify_ssl = False
        config.cert = (kubernetes["client-cert"], kubernetes["client-key"])

    @pytest.fixture
    def fdd(self, kubernetes):
        port = self._get_open_port()
        fdd = subprocess.Popen(["fiaas-deploy-daemon",
                                "--no-proxy", "--debug",
                                "--port", str(port),
                                "--api-server", kubernetes["server"],
                                "--client-cert", kubernetes["client-cert"],
                                "--client-key", kubernetes["client-key"],
                                "--target-cluster", "test"
                                ])
        time.sleep(1)
        yield "http://localhost:{}/fiaas".format(port)
        self._end_popen(fdd)

    @pytest.fixture
    def fiaas_yml(self, request):
        port = self._get_open_port()
        data_dir = request.fspath.dirpath().join("specs", "data")
        httpd = subprocess.Popen(["python", "-m", "SimpleHTTPServer", str(port)],
                                 cwd=data_dir.strpath)
        time.sleep(1)
        yield "http://127.0.0.1:{}/has_secrets.yml".format(port)
        self._end_popen(httpd)

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

    def test_post_to_web(self, fdd, fiaas_yml):
        data = {
            "fiaas-name": NAME,
            "fiaas-image": IMAGE,
            "fiaas-fiaas": fiaas_yml
        }
        resp = requests.post(fdd, data)
        resp.raise_for_status()

        time.sleep(5)
        Service.get(NAME)
        Ingress.get(NAME)
        Deployment.get(NAME)
