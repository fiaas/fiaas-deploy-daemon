#!/usr/bin/env python
# -*- coding: utf-8

import contextlib
import socket
import subprocess
import time

import pytest
import re
import requests
import yaml
from k8s import config
from k8s.client import NotFound
from k8s.models.deployment import Deployment
from k8s.models.ingress import Ingress
from k8s.models.service import Service

IMAGE1 = "finntech/application-name:123"
IMAGE2 = "finntech/application-name:321"


def _has_utilities():
    try:
        subprocess.check_call(["minikube", "version"])
        subprocess.check_call(["kubectl", "version", "--client"])
    except (subprocess.CalledProcessError, OSError):
        return False
    return True


@pytest.mark.skipif(not _has_utilities(), reason="E2E test requires minikube and kubectl installed on the PATH")
@pytest.mark.integration_test
class TestE2E(object):
    @pytest.fixture(scope="module")
    def kubernetes(self):
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
            subprocess.call(["minikube", "start"])
            time.sleep(5)
            running = (subprocess.call(["kubectl", "cluster-info"]) == 0)
        if not running:
            raise RuntimeError("Minikube won't start")

    @pytest.fixture(autouse=True)
    def k8s_client(self, kubernetes):
        config.api_server = kubernetes["server"]
        config.debug = True
        config.verify_ssl = False
        config.cert = (kubernetes["client-cert"], kubernetes["client-key"])

    @pytest.fixture(scope="module")
    def fdd(self, kubernetes):
        port = self._get_open_port()
        fdd = subprocess.Popen(["fiaas-deploy-daemon",
                                "--no-proxy", "--debug",
                                "--port", str(port),
                                "--api-server", kubernetes["server"],
                                "--client-cert", kubernetes["client-cert"],
                                "--client-key", kubernetes["client-key"],
                                "--environment", "test"
                                ])
        time.sleep(1)
        yield "http://localhost:{}/fiaas".format(port)
        self._end_popen(fdd)

    @pytest.fixture(params=(
            "data/v1minimal.yml",
            "data/v2minimal.yml",
            "v2/data/host.yml",
            "v2/data/exec_config.yml"
    ))
    def fiaas_yml(self, request):
        port = self._get_open_port()
        data_dir = request.fspath.dirpath().join("specs")
        httpd = subprocess.Popen(["python", "-m", "SimpleHTTPServer", str(port)],
                                 cwd=data_dir.strpath)
        time.sleep(1)
        yield (self._sanitize(request.param), "http://localhost:{}/{}".format(port, request.param))
        self._end_popen(httpd)

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

    def test_post_to_web(self, fdd, fiaas_yml):
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
            "teams": "testteam",
            "tags": "testtags"
        }
        resp = requests.post(fdd, data)
        resp.raise_for_status()

        # Check deploy success
        time.sleep(5)
        for kind in kinds:
            assert kind.get(name)
        dep = Deployment.get(name)
        assert dep.spec.template.spec.containers[0].image == IMAGE1

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
