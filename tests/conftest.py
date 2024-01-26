#!/usr/bin/env python
# -*- coding: utf-8

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
import itertools
import os
import re
import subprocess
import uuid as uuidlib

import pytest
from xdist.scheduler import LoadScopeScheduling

DOCKER_FOR_E2E_OPTION = "--use-docker-for-e2e"
E2E_K8S_VERSION_OPTION = "--e2e-k8s-version"

pytest_plugins = ["helpers_namespace"]


def uuid():
    return str(uuidlib.uuid4())[:8]


@pytest.fixture(autouse=True)
def prometheus_registry():
    from prometheus_client.core import REGISTRY

    yield REGISTRY
    for c in list(REGISTRY._collector_to_names.keys()):
        REGISTRY.unregister(c)


@pytest.helpers.register
def assert_any_call(mockk, first, *args, **kwargs):
    __tracebackhide__ = True

    def _assertion():
        mockk.assert_any_call(first, *args, **kwargs)

    _add_useful_error_message(_assertion, mockk, first, args)


@pytest.helpers.register
def assert_no_calls(mockk, uri=None):
    __tracebackhide__ = True

    def _assertion():
        calls = [call[0] for call in mockk.call_args_list if (uri is None or call[0][0] == uri)]
        assert len(calls) == 0

    _add_useful_error_message(_assertion, mockk, None, None)


@pytest.helpers.register
def assert_dicts(actual, expected):
    __tracebackhide__ = True

    try:
        assert actual == expected
    except AssertionError:
        raise AssertionError(_add_argument_diff(actual, expected))


def _add_useful_error_message(assertion, mockk, first, args):
    """
    If an AssertionError is raised in the assert, find any other calls on mock where the first parameter is uri and
    append those calls to the AssertionErrors message to more easily find the cause of the test failure.
    """
    __tracebackhide__ = True
    try:
        assertion()
    except AssertionError:
        other_calls = [call[0] for call in mockk.call_args_list if (first is None or call[0][0] == first)]
        if other_calls:
            extra_info = "\n\nURI {} got the following other calls:\n{}\n".format(
                first, "\n".join(_format_call(call) for call in other_calls)
            )
            if len(other_calls) == 1 and len(other_calls[0]) == 2 and args is not None:
                extra_info += _add_argument_diff(other_calls[0][1], args[0])
            raise AssertionError(extra_info)
        else:
            raise


def _add_argument_diff(actual, expected, indent=0, acc=None):
    first = False
    if not acc:
        acc = ["Actual vs Expected"]
        first = True
    if type(actual) != type(expected):
        acc.append("{}{!r} {} {!r}".format(" " * indent * 2, actual, "==" if actual == expected else "!=", expected))
    elif isinstance(actual, dict):
        for k in set(list(actual.keys()) + list(expected.keys())):
            acc.append("{}{}:".format(" " * indent * 2, k))
            a = actual.get(k)
            e = expected.get(k)
            if a != e:
                _add_argument_diff(a, e, indent + 1, acc)
    elif isinstance(actual, list):
        for a, e in itertools.zip_longest(actual, expected):
            acc.append("{}-".format(" " * indent * 2))
            if a != e:
                _add_argument_diff(a, e, indent + 1, acc)
    else:
        acc.append("{}{!r} {} {!r}".format(" " * indent * 2, actual, "==" if actual == expected else "!=", expected))
    if first:
        return "\n".join(acc)


def _format_call(call):
    if len(call) > 1:
        return "call({}, {})".format(call[0], call[1])
    else:
        return "call({})".format(call[0])


class FixtureScheduling(LoadScopeScheduling):
    def __init__(self, config, log=None):
        LoadScopeScheduling.__init__(self, config, log)
        self._assigned_scope = {}

    def _split_scope(self, nodeid):
        if nodeid in self._assigned_scope:
            return self._assigned_scope[nodeid]
        m = re.search(r".*\[(.*)\].*", nodeid)
        if not m:
            scope = LoadScopeScheduling._split_scope(self, nodeid)
        else:
            fixture_values = m.group(1).split("-")
            if "test_e2e.py" in nodeid:
                scope = self._select_scope_e2e(nodeid, fixture_values)
            else:
                scope = self._select_scope(fixture_values)
        self._assigned_scope[nodeid] = scope
        return scope

    def _select_scope(self, fixture_values):
        groups = itertools.zip_longest(fillvalue="", *([iter(fixture_values)] * 3))
        return "-".join(next(groups))

    def _select_scope_e2e(self, nodeid, fixture_values):
        """Kubernetes cluster startup time for the e2e tests in test_e2e.py is significant. To ensure tests that use
        the same cluster run on the same worker, group tests from test_e2e.py by the cluster the test needs, by
        setting the same scope for tests that use the same cluster. This should avoid two different workers spinning
        up the same type of cluster to run tests against separately.

        There are currently 3 cluster types used by the e2e tests;
        - kubernetes with NodePort service_type,
        - kubernetes with ClusterIP service_type
        - kubernetes_service_account

        Scopes:
        - group tests with NodePort or ClusterIP in fixture_values to use kubernetes/NodePort or kubernetes/ClusterIP
        respectively
        - group tests which contain test_custom_resource_definition_deploy_with_service_account together to use
        kubernetes_service_account
        - if none of those apply, use the previous behavior of grouping by the two first fixture names (this is just
        as a fallback and might lead to suboptimal scheduling).
        """
        if "test_custom_resource_definition_deploy_with_service_account" in nodeid:
            return "serviceaccount"

        for service_type in ("NodePort", "ClusterIP"):
            if service_type in fixture_values:
                return service_type

        return "-".join(fixture_values[:2])


@pytest.hookimpl(tryfirst=True)
def pytest_xdist_make_scheduler(config, log):
    return FixtureScheduling(config, log)


def pytest_addoption(parser):
    parser.addoption(
        DOCKER_FOR_E2E_OPTION,
        action="store_true",
        help="Run FDD using the development container image when executing E2E tests",
    )
    # When changing the most recent Kubernetes version here, also update the most recent Kubernetes version used in CI
    # in .semaphore/semaphore.yml, as these should point to the same version.
    parser.addoption(
        E2E_K8S_VERSION_OPTION,
        action="store",
        default="v1.27.3",
        help="Run e2e tests against a kind cluster using this Kubernetes version",
    )


@pytest.fixture(scope="session")
def k8s_version(request):
    return request.config.getoption(E2E_K8S_VERSION_OPTION)


@pytest.fixture(scope="session")
def use_docker_for_e2e(request):
    def dockerize(test_request, cert_path, service_type, k8s_version, port, apiserver_ip):
        container_name = "fdd_{}_{}_{}".format(service_type, k8s_version, uuid())
        test_request.addfinalizer(lambda: subprocess.call(["docker", "stop", container_name]))
        args = [
            "docker",
            "run",
            "-i",
            "--rm",
            "-e",
            "NAMESPACE",
            "--name",
            container_name,
            "--network=kind",
            "--publish",
            "{port}:{port}".format(port=port),
            "--mount",
            "type=bind,src={},dst={},ro".format(cert_path, cert_path),
            # make `kubernetes` resolve to the apiserver's IP to make it possible to validate its TLS cert
            "--add-host",
            "kubernetes:{}".format(apiserver_ip),
        ]
        return args + ["fiaas/fiaas-deploy-daemon:development"]

    if request.config.getoption(DOCKER_FOR_E2E_OPTION):
        return dockerize
    else:
        return lambda *args, **kwargs: []


def _is_macos():
    return os.uname()[0] == "Darwin"
