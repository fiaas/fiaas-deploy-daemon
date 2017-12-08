#!/usr/bin/env python
# -*- coding: utf-8

from __future__ import print_function

import contextlib
import socket
import subprocess
import sys
import time
import traceback
from copy import deepcopy
from datetime import datetime
from distutils.version import StrictVersion
from urlparse import urljoin

import pytest
import re
import requests
import yaml
from k8s import config
from k8s.client import NotFound, Client
from k8s.models.autoscaler import HorizontalPodAutoscaler
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


def _fixture_names(fixture_value):
    name, data = fixture_value
    return name


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
                "--datadog-container-image", "DATADOG_IMAGE",
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

    @pytest.fixture(ids=_fixture_names, params=(
            ("data/v2minimal.yml", {
                Service: "e2e_expected/v2minimal-service.yml",
                Deployment: "e2e_expected/v2minimal-deployment.yml",
                Ingress: "e2e_expected/v2minimal-ingress.yml",
            }),
            ("v2/data/examples/host.yml", {
                Service: "e2e_expected/host-service.yml",
                Deployment: "e2e_expected/host-deployment.yml",
                Ingress: "e2e_expected/host-ingress.yml",
            }),
            ("v2/data/examples/exec_config.yml", {
                Service: "e2e_expected/exec-service.yml",
                Deployment: "e2e_expected/exec-deployment.yml",
                Ingress: "e2e_expected/exec-ingress.yml",
            }),
            ("v2/data/examples/tcp_ports.yml", {
                Service: "e2e_expected/tcp_ports-service.yml",
                Deployment: "e2e_expected/tcp_ports-deployment.yml",
            }),
            ("v2/data/examples/single_tcp_port.yml", {
                Service: "e2e_expected/single_tcp_port-service.yml",
                Deployment: "e2e_expected/single_tcp_port-deployment.yml",
            }),
            ("v2/data/examples/partial_override.yml", {
                Service: "e2e_expected/partial_override-service.yml",
                Deployment: "e2e_expected/partial_override-deployment.yml",
                Ingress: "e2e_expected/partial_override-ingress.yml",
                HorizontalPodAutoscaler: "e2e_expected/partial_override-hpa.yml",
            }),
            ("v3/data/examples/v3minimal.yml", {
                Service: "e2e_expected/v3minimal-service.yml",
                Deployment: "e2e_expected/v3minimal-deployment.yml",
                Ingress: "e2e_expected/v3minimal-ingress.yml",
                HorizontalPodAutoscaler: "e2e_expected/v3minimal-hpa.yml",
            }),
            ("v3/data/examples/full.yml", {
                Service: "e2e_expected/v3full-service.yml",
                Deployment: "e2e_expected/v3full-deployment.yml",
                Ingress: "e2e_expected/v3full-ingress.yml",
                HorizontalPodAutoscaler: "e2e_expected/v3full-hpa.yml",
            }),
            ("v3/data/examples/multiple_hosts_multiple_paths.yml", {
                Service: "e2e_expected/multiple_hosts_multiple_paths-service.yml",
                Deployment: "e2e_expected/multiple_hosts_multiple_paths-deployment.yml",
                Ingress: "e2e_expected/multiple_hosts_multiple_paths-ingress.yml",
                HorizontalPodAutoscaler: "e2e_expected/multiple_hosts_multiple_paths-hpa.yml",
            }),
    ))
    def third_party_resource(self, request, k8s_version):
        fiaas_path, expected = request.param
        _skip_if_tpr_not_supported(k8s_version)

        fiaas_yml = _read_yml(request.fspath.dirpath().join("specs").join(fiaas_path).strpath)
        expected = {kind: _read_yml(request.fspath.dirpath().join(path).strpath) for kind, path in expected.items()}

        name = self._sanitize(fiaas_path)
        metadata = ObjectMeta(name=name, namespace="default", labels={"fiaas/deployment_id": DEPLOYMENT_ID1})
        spec = PaasbetaApplicationSpec(application=name, image=IMAGE1, config=fiaas_yml)
        return name, PaasbetaApplication(metadata=metadata, spec=spec), expected

    @pytest.fixture(ids=_fixture_names, params=(
            ("data/v2minimal.yml", {
                Service: "e2e_expected/v2minimal-service.yml",
                Deployment: "e2e_expected/v2minimal-deployment.yml",
                Ingress: "e2e_expected/v2minimal-ingress.yml",
            }),
            ("v2/data/examples/host.yml", {
                Service: "e2e_expected/host-service.yml",
                Deployment: "e2e_expected/host-deployment.yml",
                Ingress: "e2e_expected/host-ingress.yml",
            }),
            ("v2/data/examples/exec_config.yml", {
                Service: "e2e_expected/exec-service.yml",
                Deployment: "e2e_expected/exec-deployment.yml",
                Ingress: "e2e_expected/exec-ingress.yml",
            }),
            ("v2/data/examples/tcp_ports.yml", {
                Service: "e2e_expected/tcp_ports-service.yml",
                Deployment: "e2e_expected/tcp_ports-deployment.yml",
            }),
            ("v2/data/examples/single_tcp_port.yml", {
                Service: "e2e_expected/single_tcp_port-service.yml",
                Deployment: "e2e_expected/single_tcp_port-deployment.yml",
            }),
            ("v2/data/examples/partial_override.yml", {
                Service: "e2e_expected/partial_override-service.yml",
                Deployment: "e2e_expected/partial_override-deployment.yml",
                Ingress: "e2e_expected/partial_override-ingress.yml",
                HorizontalPodAutoscaler: "e2e_expected/partial_override-hpa.yml",
            }),
            ("v3/data/examples/v3minimal.yml", {
                Service: "e2e_expected/v3minimal-service.yml",
                Deployment: "e2e_expected/v3minimal-deployment.yml",
                Ingress: "e2e_expected/v3minimal-ingress.yml",
                HorizontalPodAutoscaler: "e2e_expected/v3minimal-hpa.yml",
            }),
            ("v3/data/examples/full.yml", {
                Service: "e2e_expected/v3full-service.yml",
                Deployment: "e2e_expected/v3full-deployment.yml",
                Ingress: "e2e_expected/v3full-ingress.yml",
                HorizontalPodAutoscaler: "e2e_expected/v3full-hpa.yml",
            }),
            ("v3/data/examples/multiple_hosts_multiple_paths.yml", {
                Service: "e2e_expected/multiple_hosts_multiple_paths-service.yml",
                Deployment: "e2e_expected/multiple_hosts_multiple_paths-deployment.yml",
                Ingress: "e2e_expected/multiple_hosts_multiple_paths-ingress.yml",
                HorizontalPodAutoscaler: "e2e_expected/multiple_hosts_multiple_paths-hpa.yml",
            }),
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
    def _select_kinds(expected):
        if len(expected.keys()) > 0:
            return expected.keys()
        else:
            return [Service, Deployment, Ingress]

    @pytest.mark.usefixtures("fdd")
    def test_third_party_resource_deploy(self, third_party_resource, service_type):
        name, paasbetaapplication, expected = third_party_resource

        # check that k8s objects for name doesn't already exist
        kinds = self._select_kinds(expected)
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
        kinds = self._select_kinds(expected)
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
    actual_dict = deepcopy(resource.as_dict())
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
    del expected_dict['apiVersion']
    del expected_dict['kind']

    # delete auto-generated k8s fields that we can't control in test data and/or don't care about testing
    _ensure_key_missing(actual_dict, "metadata", "creationTimestamp")  # the time at which the resource was created
    # indicates how many times the resource has been modified
    _ensure_key_missing(actual_dict, "metadata", "generation")
    # resourceVersion is used to handle concurrent updates to the same resource
    _ensure_key_missing(actual_dict, "metadata", "resourceVersion")
    _ensure_key_missing(actual_dict, "metadata", "selfLink")   # a API link to the resource itself
    # a unique id randomly for the resource generated on the Kubernetes side
    _ensure_key_missing(actual_dict, "metadata", "uid")
    # an internal annotation used to track ReplicaSets tied to a particular version of a Deployment
    _ensure_key_missing(actual_dict, "metadata", "annotations", "deployment.kubernetes.io/revision")
    # status is managed by Kubernetes itself, and is not part of the configuration of the resource
    _ensure_key_missing(actual_dict, "status")
    if isinstance(resource, Service):
        _ensure_key_missing(actual_dict, "spec", "clusterIP")  # an available ip is picked randomly
        for port in actual_dict["spec"]["ports"]:
            _ensure_key_missing(port, "nodePort")  # an available port is randomly picked from the nodePort range

    pytest.helpers.assert_dicts(actual_dict, expected_dict)


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
