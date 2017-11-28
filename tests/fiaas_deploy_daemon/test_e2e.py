#!/usr/bin/env python
# -*- coding: utf-8

from __future__ import print_function

import contextlib
from copy import deepcopy
import socket
import subprocess
import sys
import time
import traceback
from datetime import datetime
from distutils.version import StrictVersion
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

from fiaas_deploy_daemon.crd.types import FiaasApplication, FiaasStatus, FiaasApplicationSpec
from fiaas_deploy_daemon.tpr.status import create_name
from fiaas_deploy_daemon.tpr.types import PaasbetaApplication, PaasbetaApplicationSpec, PaasbetaStatus
from minikube import MinikubeInstaller, MinikubeError
from minikube.drivers import MinikubeDriverError

IMAGE1 = u"finntech/application-name:123"
IMAGE2 = u"finntech/application-name:321"
DEPLOYMENT_ID1 = u"deployment_id_1"
DEPLOYMENT_ID2 = u"deployment_id_2"
PATIENCE = 300
TIMEOUT = 5


def _wait_until(action, description=None, exception_class=AssertionError, patience=PATIENCE):
    """Attempt to call 'action' every 2 seconds, until it completes without exception or patience runs out"""
    __tracebackhide__ = True

    start = time_monotonic()
    cause = []
    if not description:
        description = action.__doc__ or action.__name__
    message = []
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
    header = "Gave up waiting for {} after {} seconds at {}".format(description, patience, datetime.now().isoformat(" "))
    message.insert(0, header)
    raise exception_class("".join(message))


def _tpr_available(kubernetes):
    app_url = urljoin(kubernetes["server"], PaasbetaApplication._meta.url_template.format(namespace="default", name=""))
    status_url = urljoin(kubernetes["server"], PaasbetaStatus._meta.url_template.format(namespace="default", name=""))
    session = requests.Session()
    session.verify = kubernetes["api-cert"]
    session.cert = (kubernetes["client-cert"], kubernetes["client-key"])

    def tpr_available():
        plog("Checking if TPRs are available")
        for url in (app_url, status_url):
            plog("Checking %s" % url)
            resp = session.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            plog("!!!!! %s is available !!!!" % url)

    return tpr_available


def _crd_available(kubernetes):
    app_url = urljoin(kubernetes["server"], FiaasApplication._meta.url_template.format(namespace="default", name=""))
    status_url = urljoin(kubernetes["server"], FiaasStatus._meta.url_template.format(namespace="default", name=""))
    session = requests.Session()
    session.verify = kubernetes["api-cert"]
    session.cert = (kubernetes["client-cert"], kubernetes["client-key"])

    def crd_available():
        plog("Checking if CRDs are available")
        for url in (app_url, status_url):
            plog("Checking %s" % url)
            resp = session.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            plog("!!!!! %s is available !!!!" % url)

    return crd_available


@pytest.fixture(scope="session")
def minikube_installer():
    try:
        mki = MinikubeInstaller()
        mki.install()
        yield mki
        mki.cleanup()
    except MinikubeDriverError as e:
        pytest.skip(str(e))
    except MinikubeError as e:
        msg = "Unable to install minikube: %s"
        pytest.fail(msg % str(e))


@pytest.fixture(scope="session", params=("ClusterIP", "NodePort"))
def service_type(request):
    return request.param


@pytest.mark.integration_test
class TestE2E(object):
    @pytest.fixture(scope="module", params=("v1.6.4", "v1.7.5", "v1.8.0"))
    def k8s_version(self, request):
        yield request.param

    @pytest.fixture(scope="module")
    def kubernetes(self, minikube_installer, service_type, k8s_version):
        try:
            minikube = minikube_installer.new(profile=service_type, k8s_version=k8s_version)
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

    @pytest.fixture(scope="module")
    def fdd(self, kubernetes, service_type, k8s_version):
        port = self._get_open_port()
        args = ["fiaas-deploy-daemon",
                "--port", str(port),
                "--api-server", kubernetes["server"],
                "--api-cert", kubernetes["api-cert"],
                "--client-cert", kubernetes["client-cert"],
                "--client-key", kubernetes["client-key"],
                "--service-type", service_type,
                "--ingress-suffix", "svc.test.example.com",
                "--environment", "test",
                ]
        if _tpr_supported(k8s_version):
            args.append("--enable-tpr-support")
        if _crd_supported(k8s_version):
            args.append("--enable-crd-support")
        fdd = subprocess.Popen(args)

        def ready():
            resp = requests.get("http://localhost:{}/healthz".format(port), timeout=TIMEOUT)
            resp.raise_for_status()

        try:
            _wait_until(ready, "web-interface healthy", RuntimeError)
            if _tpr_supported(k8s_version):
                _wait_until(_tpr_available(kubernetes), "TPR available", RuntimeError)
            if _crd_supported(k8s_version):
                _wait_until(_crd_available(kubernetes), "CRD available", RuntimeError)
            yield "http://localhost:{}/fiaas".format(port)
        finally:
            self._end_popen(fdd)

    @pytest.fixture(params=(
            "data/v2minimal.yml",
            "v2/data/examples/host.yml",
            "v2/data/examples/exec_config.yml",
    ))
    def fiaas_yml(self, request):
        port = self._get_open_port()
        data_dir = request.fspath.dirpath().join("specs")
        httpd = subprocess.Popen(["python", "-m", "SimpleHTTPServer", str(port)],
                                 cwd=data_dir.strpath)
        fiaas_yml_url = "http://localhost:{}/{}".format(port, request.param)

        try:
            def ready():
                resp = requests.get(fiaas_yml_url, timeout=TIMEOUT)
                resp.raise_for_status()

            _wait_until(ready, "web-interface healthy", RuntimeError)
            yield (self._sanitize(request.param), fiaas_yml_url)
        finally:
            self._end_popen(httpd)

    @pytest.fixture(params=(
            "data/v2minimal.yml",
            "v2/data/examples/host.yml",
            "v2/data/examples/exec_config.yml",
    ))
    def third_party_resource(self, request, k8s_version):
        _skip_if_tpr_not_supported(k8s_version)
        fiaas_yml_path = request.fspath.dirpath().join("specs").join(request.param).strpath
        with open(fiaas_yml_path, 'r') as fobj:
            fiaas_yml = yaml.safe_load(fobj)

        name = self._sanitize(request.param)
        metadata = ObjectMeta(name=name, namespace="default", labels={"fiaas/deployment_id": DEPLOYMENT_ID1})
        spec = PaasbetaApplicationSpec(application=name, image=IMAGE1,
                                       config=fiaas_yml)
        return name, PaasbetaApplication(metadata=metadata, spec=spec)

    @pytest.fixture(params=(
            ("data/v2minimal.yml", {
                Service: "e2e_expected/v2minimal-service.yml",
                Deployment: "e2e_expected/v2minimal-deployment.yml",
            }),
            ("v2/data/examples/host.yml", {}),
            ("v2/data/examples/exec_config.yml", {}),
    ))
    def custom_resource_definition(self, request, k8s_version):
        fiaas_path, expected = request.param

        _skip_if_crd_not_supported(k8s_version)
        fiaas_yml = _read_yml(request.fspath.dirpath().join("specs").join(fiaas_path).strpath)
        expected = {kind: _read_yml(request.fspath.dirpath().join(path).strpath) for kind, path in expected.items()}

        name = self._sanitize(fiaas_path)
        metadata = ObjectMeta(name=name, namespace="default", labels={"fiaas/deployment_id": DEPLOYMENT_ID1})
        spec = FiaasApplicationSpec(application=name, image=IMAGE1, config=fiaas_yml)
        return name, FiaasApplication(metadata=metadata, spec=spec), expected

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
        expected = {}
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
        _wait_until(_deploy_success(name, kinds, service_type, IMAGE1, expected, DEPLOYMENT_ID1))

        # Redeploy, new image
        data["image"] = IMAGE2
        resp = requests.post(fdd, data)
        resp.raise_for_status()

        # Check redeploy success
        _wait_until(_deploy_success(name, kinds, service_type, IMAGE2, expected, DEPLOYMENT_ID2))

        # Cleanup
        for kind in kinds:
            kind.delete(name)

    @pytest.mark.usefixtures("fdd")
    def test_third_party_resource_deploy(self, third_party_resource, service_type):
        name, paasbetaapplication = third_party_resource
        expected = {}

        # check that k8s objects for name doesn't already exist
        kinds = self._select_kinds(name)
        for kind in kinds:
            with pytest.raises(NotFound):
                kind.get(name)

        # First deploy
        paasbetaapplication.save()

        # Check that deployment status is RUNNING
        def _assert_status():
            status = PaasbetaStatus.get(create_name(name, DEPLOYMENT_ID1))
            assert status.result == u"RUNNING"

        _wait_until(_assert_status)

        # Check deploy success
        _wait_until(_deploy_success(name, kinds, service_type, IMAGE1, expected, DEPLOYMENT_ID1))

        # Redeploy, new image
        paasbetaapplication.spec.image = IMAGE2
        paasbetaapplication.metadata.labels["fiaas/deployment_id"] = DEPLOYMENT_ID2
        paasbetaapplication.save()

        # Check success
        _wait_until(_deploy_success(name, kinds, service_type, IMAGE2, expected, DEPLOYMENT_ID2))

        # Cleanup
        PaasbetaApplication.delete(name)

        def cleanup_complete():
            for kind in kinds:
                with pytest.raises(NotFound):
                    kind.get(name)

        _wait_until(cleanup_complete)

    @pytest.mark.usefixtures("fdd")
    def test_custom_resource_definition_deploy(self, custom_resource_definition, service_type):
        name, fiaas_application, expected = custom_resource_definition

        # check that k8s objects for name doesn't already exist
        kinds = self._select_kinds(name)
        for kind in kinds:
            with pytest.raises(NotFound):
                kind.get(name)

        # First deploy
        fiaas_application.save()

        # Check that deployment status is RUNNING
        def _assert_status():
            status = FiaasStatus.get(create_name(name, DEPLOYMENT_ID1))
            assert status.result == u"RUNNING"

        _wait_until(_assert_status)

        # Check deploy success
        _wait_until(_deploy_success(name, kinds, service_type, IMAGE1, expected, DEPLOYMENT_ID1))

        # Redeploy, new image
        fiaas_application.spec.image = IMAGE2
        fiaas_application.metadata.labels["fiaas/deployment_id"] = DEPLOYMENT_ID2
        fiaas_application.save()

        # Check success
        _wait_until(_deploy_success(name, kinds, service_type, IMAGE2, expected, DEPLOYMENT_ID2))

        # Cleanup
        FiaasApplication.delete(name)

        def cleanup_complete():
            for kind in kinds:
                with pytest.raises(NotFound):
                    kind.get(name)

        _wait_until(cleanup_complete)


def _deploy_success(name, kinds, service_type, image, expected, deployment_id):
    def action():
        for kind in kinds:
            assert kind.get(name)
        dep = Deployment.get(name)
        assert dep.spec.template.spec.containers[0].image == image
        svc = Service.get(name)
        assert svc.spec.type == service_type

        for kind, expected_dict in expected.items():
            actual = kind.get(name)
            _assert_k8s_resource_matches(actual, expected_dict, image, service_type, deployment_id)

    return action


def _skip_if_tpr_not_supported(k8s_version):
    if not _tpr_supported(k8s_version):
        pytest.skip("TPR not supported in version %s of kubernetes, skipping this test" % k8s_version)


def _skip_if_crd_not_supported(k8s_version):
    if not _crd_supported(k8s_version):
        pytest.skip("CRD not supported in version %s of kubernetes, skipping this test" % k8s_version)


def _tpr_supported(k8s_version):
    return StrictVersion("1.6.0") <= StrictVersion(k8s_version[1:]) < StrictVersion("1.8.0")


def _crd_supported(k8s_version):
    return StrictVersion("1.7.0") <= StrictVersion(k8s_version[1:])


def plog(message):
    """Primitive logging"""
    print("%s: %s" % (time.asctime(), message))


def _read_yml(yml_path):
    with open(yml_path, 'r') as fobj:
        yml = yaml.safe_load(fobj)
    return yml


def _assert_k8s_resource_matches(resource, expected_dict, image, service_type, deployment_id):
    actual_dict = resource.as_dict()
    expected_dict = deepcopy(expected_dict)

    # set expected test parameters
    _set_labels(expected_dict, image, deployment_id)

    if expected_dict["kind"] == "Deployment":
        _set_image(expected_dict, image)
        _set_env(expected_dict, image)
        _set_labels(expected_dict["spec"]["template"], image, deployment_id)

    if expected_dict["kind"] == "Service":
        _set_service_type(expected_dict, service_type)

    # the k8s client library doesn't return apiVersion or kind, so ignore those fields
    _ensure_key_missing(expected_dict, 'apiVersion')
    _ensure_key_missing(expected_dict, 'kind')

    plog("actual_dict: {}".format(actual_dict))
    plog("expected_dict: {}".format(expected_dict))

    pytest.helpers.deep_assert_dicts(actual_dict, expected_dict)


def _set_image(expected_dict, image):
    expected_dict["spec"]["template"]["spec"]["containers"][0]["image"] = image


def _set_env(expected_dict, image):
    def generate_updated_env():
        for item in expected_dict["spec"]["template"]["spec"]["containers"][0]["env"]:
            if item["name"] == "VERSION":
                item["value"] = image.split(":")[-1]
            if item["name"] == "IMAGE":
                item["value"] = image
            yield item
    expected_dict["spec"]["template"]["spec"]["containers"][0]["env"] = list(generate_updated_env())


def _set_labels(expected_dict, image, deployment_id):
    expected_dict["metadata"]["labels"]["fiaas/version"] = image.split(":")[-1]
    expected_dict["metadata"]["labels"]["fiaas/deployment_id"] = deployment_id


def _set_service_type(expected_dict, service_type):
    expected_dict["spec"]["type"] = service_type


def _ensure_key_missing(d, *keys):
    key = keys[0]
    try:
        if len(keys) > 1:
            _ensure_key_missing(d[key], *keys[1:])
        else:
            del d[key]
    except KeyError:
        pass  # key was already missing
