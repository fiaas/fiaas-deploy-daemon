
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


import base64
import contextlib
import os
import re
import socket
import sys
import tempfile
import time
import traceback
from copy import deepcopy
from collections import defaultdict
from datetime import datetime
from urllib.parse import urljoin

import docker
import pytest
import requests
import yaml
from distutils.version import StrictVersion
from k8s.models.autoscaler import HorizontalPodAutoscaler
from k8s.models.deployment import Deployment
from k8s.models.service import Service
from monotonic import monotonic as time_monotonic

from fiaas_deploy_daemon.crd.types import FiaasApplication, FiaasApplicationStatus


def plog(message, **kwargs):
    """Primitive logging"""
    print("%s: %s" % (time.asctime(), message), file=sys.stderr, **kwargs)  # noqa: T001


def wait_until(action, description=None, exception_class=AssertionError, patience=60):
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
    header = "Gave up waiting for {} after {} seconds at {}".format(description, patience,
                                                                    datetime.now().isoformat(" "))
    message.insert(0, header)
    raise exception_class("".join(message))


def crd_available(kubernetes, timeout=5):
    app_url = urljoin(kubernetes["host-to-container-server"], FiaasApplication._meta.url_template.format(namespace="default", name=""))
    status_url = urljoin(kubernetes["host-to-container-server"],
                         FiaasApplicationStatus._meta.url_template.format(namespace="default", name=""))
    session = requests.Session()
    session.verify = kubernetes["api-cert"]
    session.cert = (kubernetes["client-cert"], kubernetes["client-key"])

    def _crd_available():
        plog("Checking if CRDs are available")
        for url in (app_url, status_url):
            plog("Checking %s" % url)
            resp = session.get(url, timeout=timeout)
            resp.raise_for_status()
            plog("!!!!! %s is available !!!!" % url)

    return _crd_available


def crd_supported(k8s_version):
    return StrictVersion("1.7.0") <= StrictVersion(k8s_version[1:])


def skip_if_crd_not_supported(k8s_version):
    if not crd_supported(k8s_version):
        pytest.skip("CRD not supported in version %s of kubernetes, skipping this test" % k8s_version)


def read_yml(yml_path):
    with open(yml_path, 'r') as fobj:
        yml = yaml.safe_load(fobj)
    return yml


def sanitize_resource_name(yml_path):
    """must match the regex [a-z]([-a-z0-9]*[a-z0-9])?"""
    return re.sub("[^-a-z0-9]", "-", yml_path.replace(".yml", ""))


def assert_k8s_resource_matches(resource, expected_dict, image, service_type, deployment_id, strongbox_groups, app_uid=None):
    actual_dict = deepcopy(resource.as_dict())
    expected_dict = deepcopy(expected_dict)

    # set expected test parameters
    _set_labels(expected_dict, image, deployment_id)

    if expected_dict["kind"] == "Deployment":
        _set_image(expected_dict, image)
        _set_env(expected_dict, image)
        _set_labels(expected_dict["spec"]["template"], image, deployment_id)
        if strongbox_groups:
            _set_strongbox_groups(expected_dict, strongbox_groups)

    if expected_dict["kind"] == "Service":
        _set_service_type(expected_dict, service_type)

    if app_uid:
        for ref in expected_dict["metadata"]["ownerReferences"]:
            ref["uid"] = app_uid

    # the k8s client library doesn't return apiVersion or kind, so ignore those fields
    del expected_dict['apiVersion']
    del expected_dict['kind']

    # delete auto-generated k8s fields that we can't control in test data and/or don't care about testing
    _ensure_key_missing(actual_dict, "metadata", "creationTimestamp")  # the time at which the resource was created
    # indicates how many times the resource has been modified
    _ensure_key_missing(actual_dict, "metadata", "generation")
    # resourceVersion is used to handle concurrent updates to the same resource
    _ensure_key_missing(actual_dict, "metadata", "resourceVersion")
    _ensure_key_missing(actual_dict, "metadata", "selfLink")  # a API link to the resource itself
    # a unique id randomly for the resource generated on the Kubernetes side
    _ensure_key_missing(actual_dict, "metadata", "uid")
    # an internal annotation used to track ReplicaSets tied to a particular version of a Deployment
    _ensure_key_missing(actual_dict, "metadata", "annotations", "deployment.kubernetes.io/revision")
    # status is managed by Kubernetes itself, and is not part of the configuration of the resource
    _ensure_key_missing(actual_dict, "status")
    # autoscaling.alpha.kubernetes.io/conditions is automatically set when converting from
    # autoscaling/v2beta.HorizontalPodAutoscaler to autoscaling/v1.HorizontalPodAutoscaler internally in Kubernetes
    if isinstance(resource, HorizontalPodAutoscaler):
        _ensure_key_missing(actual_dict, "metadata", "annotations", "autoscaling.alpha.kubernetes.io/conditions")
    # pod.alpha.kubernetes.io/init-containers
    # pod.beta.kubernetes.io/init-containers
    # pod.alpha.kubernetes.io/init-container-statuses
    # pod.beta.kubernetes.io/init-container-statuses
    # are automatically set when converting from core.Pod to v1.Pod internally in Kubernetes (in some versions)
    if isinstance(resource, Deployment):
        _ensure_key_missing(actual_dict, "spec", "template", "metadata", "annotations",
                            "pod.alpha.kubernetes.io/init-containers")
        _ensure_key_missing(actual_dict, "spec", "template", "metadata", "annotations",
                            "pod.beta.kubernetes.io/init-containers")
        _ensure_key_missing(actual_dict, "spec", "template", "metadata", "annotations",
                            "pod.alpha.kubernetes.io/init-container-statuses")
        _ensure_key_missing(actual_dict, "spec", "template", "metadata", "annotations",
                            "pod.beta.kubernetes.io/init-container-statuses")
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
            if item["name"] == "VERSION" or item["name"] == "FIAAS_VERSION":
                item["value"] = image.split(":")[-1]
            if item["name"] == "IMAGE" or item["name"] == "FIAAS_IMAGE":
                item["value"] = image
            yield item

    expected_dict["spec"]["template"]["spec"]["containers"][0]["env"] = list(generate_updated_env())


def _set_strongbox_groups(expected_dict, strongbox_groups):
    def generate_updated_env():
        for item in expected_dict["spec"]["template"]["spec"]["initContainers"][0]["env"]:
            if item["name"] == "SECRET_GROUPS":
                item["value"] = ",".join(strongbox_groups)
            yield item

    expected_dict["spec"]["template"]["spec"]["initContainers"][0]["env"] = list(generate_updated_env())


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


def configure_mock_fail_then_success(mockk, fail=None, success=None, fail_times=1):
    if fail is None:
        fail = lambda *args, **kwargs: None  # noqa: E731
    if success is None:
        success = lambda *args, **kwargs: None  # noqa: E731

    def _function_generator():
        for _ in range(fail_times):
            yield fail
        while True:
            yield success

    gen = _function_generator()

    def _function():
        return next(gen)()

    mockk.side_effect = _function


def get_unbound_port():
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class KindWrapper(object):
    DOCKER_IMAGES = defaultdict(lambda: "bsycorp/kind")
    # old bsycorp/kind versions isn't being updated, and the latest version has an expired cert
    # See https://github.com/fiaas/fiaas-deploy-daemon/pull/45
    DOCKER_IMAGES["v1.9.11"] = "fiaas/kind"
    # See https://github.com/fiaas/fiaas-deploy-daemon/issues/115
    DOCKER_IMAGES["v1.12.10"] = "fiaas/kind"

    def __init__(self, k8s_version, name):
        self.k8s_version = k8s_version
        self.name = name
        # on Docker for mac, directories under $TMPDIR can't be mounted by default. use /tmp, which works
        tmp_dir = '/tmp' if _is_macos() else None
        self._workdir = tempfile.mkdtemp(prefix="kind-{}-".format(name), dir=tmp_dir)
        self._client = docker.from_env()
        self._container = None

    def start(self):
        try:
            self._start()
            in_container_server_ip, api_port, config_port = self._get_ports()
            wait_until(self._endpoint_ready(config_port, "config"), "config available")
            resp = requests.get("http://localhost:{}/config".format(config_port))
            resp.raise_for_status()
            config = yaml.safe_load(resp.content)
            api_cert = self._save_to_file("api_cert", config["clusters"][-1]["cluster"]["certificate-authority-data"])
            client_cert = self._save_to_file("client_cert", config["users"][-1]["user"]["client-certificate-data"])
            client_key = self._save_to_file("client_key", config["users"][-1]["user"]["client-key-data"])
            result = {
                # the apiserver's IP. We need to map this to `kubernetes` in the fdd container to be able to validate
                # the TLS cert of the apiserver
                "container-to-container-server-ip": in_container_server_ip,
                # apiserver endpoint when running fdd as a container
                "container-to-container-server": "https://kubernetes:8443",
                # apiserver endpoint for k8s client in tests, or when running fdd locally
                "host-to-container-server": "https://localhost:{}".format(api_port),
                "client-cert": client_cert,
                "client-key": client_key,
                "api-cert": api_cert,
                "log_dumper": self.dump_logs,
            }
            plog("Waiting for container {} with name {} to become ready".format(self._container.id, self.name))
            wait_until(self._endpoint_ready(config_port, "kubernetes-ready"), "kubernetes ready", patience=180)
            return result
        except Exception:
            self.dump_logs()
            self.delete()
            raise

    def dump_logs(self, since=None, until=None):
        if self._container:
            logs = self._container.logs(since=since)
            plog("vvvvvvvvvvvvvvvv Output from kind container vvvvvvvvvvvvvvvv")
            if logs:
                plog(logs, end="")
            plog("^^^^^^^^^^^^^^^^ Output from kind container ^^^^^^^^^^^^^^^^")

    def delete(self):
        if self._container:
            try:
                self._container.stop()
            except docker.errors.NotFound:
                pass  # container has already stopped

    def _endpoint_ready(self, port, endpoint):
        url = "http://localhost:{}/{}".format(port, endpoint)

        def ready():
            resp = requests.get(url)
            resp.raise_for_status()

        return ready

    def _start(self):
        image_name = self.DOCKER_IMAGES[self.k8s_version]

        self._container = self._client.containers.run("{}:{}".format(image_name, self.k8s_version),
                                                      detach=True, stdout=True, stderr=True,
                                                      remove=True, auto_remove=True, privileged=True,
                                                      name=self.name, hostname=self.name,
                                                      ports={"10080/tcp": None, "8443/tcp": None})
        plog("Launched container {} with name {}".format(self._container.id, self.name))

    def _get_ports(self):
        self._container.reload()
        ip = self._container.attrs["NetworkSettings"]["IPAddress"]
        ports = self._container.attrs["NetworkSettings"]["Ports"]
        config_port = ports["10080/tcp"][-1]["HostPort"]
        api_port = ports["8443/tcp"][-1]["HostPort"]
        return ip, api_port, config_port

    def _save_to_file(self, name, data):
        raw_data = base64.b64decode(data)
        path = os.path.join(self._workdir, name)
        with open(path, "wb") as fobj:
            fobj.write(raw_data)
        return path


def _is_macos():
    return os.uname()[0] == 'Darwin'


class TypeMatcher(object):

    def __init__(self, _type):
        self._type = _type

    def __eq__(self, other):
        return isinstance(other, self._type)
