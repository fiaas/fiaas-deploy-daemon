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
from __future__ import absolute_import, unicode_literals

from Queue import Queue

import mock
import pytest
from k8s.base import WatchEvent
from k8s.client import NotFound
from k8s.watcher import Watcher
from requests import Response
from yaml import YAMLError

from fiaas_deploy_daemon.config import Configuration
from fiaas_deploy_daemon.crd import CrdWatcher
from fiaas_deploy_daemon.crd.types import FiaasApplication
from fiaas_deploy_daemon.deployer import DeployerEvent
from fiaas_deploy_daemon.lifecycle import Lifecycle
from fiaas_deploy_daemon.specs.factory import InvalidConfiguration

ADD_EVENT = {
    "object": {
        "metadata": {
            "labels": {
                "fiaas/deployment_id": "deployment_id"
            },
            "name": "example",
            "namespace": "the-namespace"
        },
        "spec": {
            "application": "example",
            "config": {
                "version": 2,
                "host": "example.com",
                "namespace": "default"
            },
            "image": "example/app"
        }
    },
    "type": WatchEvent.ADDED,
}

MODIFIED_EVENT = {
    "object": ADD_EVENT["object"],
    "type": WatchEvent.MODIFIED,
}

DELETED_EVENT = {
    "object": ADD_EVENT["object"],
    "type": WatchEvent.DELETED,
}


class TestWatcher(object):

    @pytest.fixture
    def spec_factory(self):
        with mock.patch("fiaas_deploy_daemon.specs.factory.SpecFactory") as mockk:
            yield mockk

    @pytest.fixture
    def deploy_queue(self):
        return Queue()

    @pytest.fixture
    def watcher(self):
        return mock.create_autospec(spec=Watcher, spec_set=True, instance=True)

    @pytest.fixture
    def lifecycle(self):
        return mock.create_autospec(spec=Lifecycle, spec_set=True, instance=True)

    @pytest.fixture
    def crd_watcher(self, spec_factory, deploy_queue, watcher, lifecycle):
        crd_watcher = CrdWatcher(spec_factory, deploy_queue, Configuration([]), lifecycle)
        crd_watcher._watcher = watcher
        return crd_watcher

    def test_creates_custom_resource_definition_if_not_exists_when_watching_it(self, get, post, crd_watcher, watcher):
        get.side_effect = NotFound("Something")
        watcher.watch.side_effect = NotFound("Something")

        expected_application = {
            'metadata': {
                'namespace': 'default',
                'name': 'applications.fiaas.schibsted.io',
                'ownerReferences': [],
                'finalizers': [],
            },
            'spec': {
                'version': 'v1',
                'group': 'fiaas.schibsted.io',
                'names': {
                    'shortNames': ['app', 'fa'],
                    'kind': 'Application',
                    'plural': 'applications'
                }
            }
        }
        expected_status = {
            'metadata': {
                'namespace': 'default',
                'name': 'application-statuses.fiaas.schibsted.io',
                'ownerReferences': [],
                'finalizers': [],
            },
            'spec': {
                'version': 'v1',
                'group': 'fiaas.schibsted.io',
                'names': {
                    'shortNames': ['status', 'appstatus', 'fs'],
                    'kind': 'ApplicationStatus',
                    'plural': 'application-statuses'
                }
            }
        }

        def make_response(data):
            mock_response = mock.create_autospec(Response)
            mock_response.json.return_value = data
            return mock_response

        post.side_effect = [make_response(expected_application), make_response(expected_status)]

        crd_watcher._watch(None)

        calls = [
            mock.call("/apis/apiextensions.k8s.io/v1beta1/customresourcedefinitions/", expected_application),
            mock.call("/apis/apiextensions.k8s.io/v1beta1/customresourcedefinitions/", expected_status)
        ]
        assert post.call_args_list == calls

    def test_is_able_to_watch_custom_resource_definition(self, crd_watcher, deploy_queue, watcher):
        watcher.watch.return_value = [WatchEvent(ADD_EVENT, FiaasApplication)]

        assert deploy_queue.qsize() == 0
        crd_watcher._watch(None)
        assert deploy_queue.qsize() == 1

    @pytest.mark.parametrize("event,deployer_event_type,annotations,repository", [
        (ADD_EVENT, "UPDATE", None, None),
        (ADD_EVENT, "UPDATE", {"deployment": {"fiaas/source-repository": "xyz"}}, "xyz"),
        (MODIFIED_EVENT, "UPDATE", None, None),
        (MODIFIED_EVENT, "UPDATE", {"deployment": {"fiaas/source-repository": "xyz"}}, "xyz"),
        (DELETED_EVENT, "DELETE", None, None),
    ])
    def test_deploy(self, crd_watcher, deploy_queue, spec_factory, watcher, app_spec, event, deployer_event_type, lifecycle,
                    annotations, repository):
        event["object"]["metadata"]["annotations"] = annotations
        watcher.watch.return_value = [WatchEvent(event, FiaasApplication)]

        spec = event["object"]["spec"]
        app_name = spec["application"]
        namespace = event["object"]["metadata"]["namespace"]
        deployment_id = (event["object"]["metadata"]["labels"]["fiaas/deployment_id"]
                         if deployer_event_type != "DELETE" else "deletion")

        app_spec = app_spec._replace(name=app_name, namespace=namespace, deployment_id=deployment_id)
        spec_factory.return_value = app_spec

        crd_watcher._watch(None)

        if event in [ADD_EVENT, MODIFIED_EVENT]:
            lifecycle.initiate.assert_called_once_with(app_name=event["object"]["spec"]["application"],
                                                       namespace=event["object"]["metadata"]["namespace"],
                                                       deployment_id='deployment_id',
                                                       repository=repository)

        app_config = spec["config"]
        spec_factory.assert_called_once_with(name=app_name, image=spec["image"], app_config=app_config,
                                             teams=[], tags=[],
                                             deployment_id=deployment_id,
                                             namespace=namespace)

        assert deploy_queue.qsize() == 1
        deployer_event = deploy_queue.get_nowait()
        assert deployer_event == DeployerEvent(deployer_event_type, app_spec)
        assert deploy_queue.empty()

    @pytest.mark.parametrize("namespace", [None, "default"])
    def test_watch_namespace(self, crd_watcher, watcher, namespace):
        crd_watcher._watch(namespace)
        watcher.watch.assert_called_once_with(namespace=namespace)

    @pytest.mark.parametrize("event,deployer_event_type,error,annotations,repository", [
        (ADD_EVENT, "UPDATE", YAMLError("invalid yaml"), {}, None),
        (ADD_EVENT, "UPDATE", InvalidConfiguration("invalid config"), {}, None),
        (MODIFIED_EVENT, "UPDATE", YAMLError("invalid yaml"), {}, None),
        (MODIFIED_EVENT, "UPDATE", InvalidConfiguration("invalid config"), {}, None),
        (MODIFIED_EVENT, "UPDATE", InvalidConfiguration("invalid config"),
         {"deployment": {"fiaas/source-repository": "xyz"}}, "xyz"),
    ])
    def test_deploy_reports_failure_on_exception(self, crd_watcher, deploy_queue, spec_factory, watcher, event, deployer_event_type,
                                                 error, lifecycle, annotations, repository):
        event["object"]["metadata"]["annotations"] = annotations
        watcher.watch.return_value = [WatchEvent(event, FiaasApplication)]

        spec_factory.side_effect = error

        crd_watcher._watch(None)

        lifecycle.failed.assert_called_once_with(app_name=event["object"]["spec"]["application"],
                                                 namespace=event["object"]["metadata"]["namespace"],
                                                 deployment_id='deployment_id',
                                                 repository=repository)
        assert deploy_queue.empty()
