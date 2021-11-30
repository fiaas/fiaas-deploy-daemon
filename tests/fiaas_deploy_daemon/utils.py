
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
from __future__ import print_function

import base64
import contextlib
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import traceback
import uuid as uuidlib
from copy import deepcopy
from datetime import datetime
from urlparse import urljoin

import json
import pytest
import requests
import yaml
from distutils.version import StrictVersion
from k8s.models.autoscaler import HorizontalPodAutoscaler
from k8s.models.deployment import Deployment
from k8s.models.service import Service
from monotonic import monotonic as time_monotonic

from fiaas_deploy_daemon.crd.types import FiaasApplication, FiaasApplicationStatus


def uuid():
    return str(uuidlib.uuid4())[:8]


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
    header = "Gave up waiting for {} after {} seconds at {}".format(description, patience, datetime.now().isoformat(" "))
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
        for url in (app_url, status_url):
            plog("Checking if CRDs are available at %s" % url)
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


def _fix_service(expected_dict, service_type):
    if expected_dict["kind"] == "Service":
        _set_service_type(expected_dict, service_type)


def _fix_service_account(expected_dict, actual_dict):
    if expected_dict["kind"] == "ServiceAccount":
        _ensure_key_missing(actual_dict, "secrets")


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

    _fix_service(expected_dict, service_type)
    _fix_service_account(expected_dict, actual_dict)

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
    def __init__(self, k8s_version, name):
        self.k8s_version = k8s_version
        self.name = name
        # on Docker for mac, directories under $TMPDIR can't be mounted by default. use /tmp, which works
        tmp_dir = '/tmp' if _is_macos() else None
        self._workdir = tempfile.mkdtemp(prefix="kind-{}-".format(name), dir=tmp_dir)
        self._kubeconfig = os.path.join(self._workdir, "kubeconfig")

    def start(self):
        plog("creating kubeconfig at " + self._kubeconfig)
        image_name = "kindest/node:" + self.k8s_version
        args = ["kind", "create", "cluster", "--name="+self.name, "--kubeconfig="+self._kubeconfig, "--image="+image_name, "--wait=40s"]

        self._run_cmd(args)

        api_cert, client_cert, client_key, apiserver_url = self._kubeconfig_connection_params()

        container_name = self.name + "-control-plane"
        in_container_server_ip = self._in_container_server_ip(container_name)

        result = {
            # the apiserver's IP. We need to map this to `kubernetes` in the fdd container to be able to validate
            # the TLS cert of the apiserver
            "container-to-container-server-ip": in_container_server_ip,
            # apiserver endpoint when running fdd as a container
            "container-to-container-server": "https://{}:6443".format(container_name),
            # apiserver endpoint for k8s client in tests, or when running fdd locally
            "host-to-container-server": apiserver_url,
            "client-cert": client_cert,
            "client-key": client_key,
            "api-cert": api_cert,
        }
        plog("started kind cluster at {}".format(apiserver_url))
        return result

    def _kubeconfig_connection_params(self):
        with open(self._kubeconfig, 'r') as f:
            config = yaml.safe_load(f.read())
        api_cert = self._save_to_file("api_cert", config["clusters"][-1]["cluster"]["certificate-authority-data"])
        client_cert = self._save_to_file("client_cert", config["users"][-1]["user"]["client-certificate-data"])
        client_key = self._save_to_file("client_key", config["users"][-1]["user"]["client-key-data"])
        apiserver_url = config["clusters"][-1]["cluster"]["server"]
        return api_cert, client_cert, client_key, apiserver_url

    def _in_container_server_ip(self, container_name):
        output = self._run_cmd(["docker", "inspect", container_name])
        inspect = json.loads(output)
        return inspect[0]["NetworkSettings"]["Networks"]["kind"]["IPAddress"]

    def delete(self):
        self._run_cmd(["kind", "delete", "cluster", "--name", self.name])
        plog("cluster {} deleted".format(self.name))

    def _save_to_file(self, name, data):
        raw_data = base64.b64decode(data)
        path = os.path.join(self._workdir, name)
        with open(path, "wb") as fobj:
            fobj.write(raw_data)
        return path

    def _run_cmd(self, args):
        try:
            output = subprocess.check_output(args, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            plog("vvvvvvvvvvvvvvvv Output from {} vvvvvvvvvvvvvvvv".format(args[0]))
            plog(e.output)
            plog("^^^^^^^^^^^^^^^^ Output from {} ^^^^^^^^^^^^^^^^".format(args[0]))
            raise e
        return output.strip()


def _is_macos():
    return os.uname()[0] == 'Darwin'


class TypeMatcher(object):

    def __init__(self, _type):
        self._type = _type

    def __eq__(self, other):
        return isinstance(other, self._type)
