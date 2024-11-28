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


import copy
from queue import Queue

from unittest import mock
import pytest
from k8s.base import WatchEvent
from k8s.client import NotFound
from k8s.watcher import Watcher
from yaml import YAMLError

from fiaas_deploy_daemon.config import Configuration
from fiaas_deploy_daemon.crd import CrdWatcher
from fiaas_deploy_daemon.crd.types import FiaasApplication, AdditionalLabelsOrAnnotations, FiaasApplicationStatus
from fiaas_deploy_daemon.deployer import DeployerEvent
from fiaas_deploy_daemon.lifecycle import Lifecycle, Subject
from fiaas_deploy_daemon.specs.factory import InvalidConfiguration

ADD_EVENT = {
    "object": {
        "metadata": {
            "labels": {"fiaas/deployment_id": "deployment_id"},
            "name": "example",
            "namespace": "the-namespace",
            "uid": "c1f34517-6f54-11ea-8eaf-0ad3d9992c8c",
            "generation": 1,
        },
        "spec": {
            "application": "example",
            "config": {"version": 2, "host": "example.com", "namespace": "default", "annotations": {}},
            "image": "example/app",
        },
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

STATUS_EVENT = {
    "object": {
        "metadata": {
            "labels": {"fiaas/deployment_id": "deployment_id"},
            "name": "example",
            "namespace": "the-namespace",
            "uid": "c1f34517-6f54-11ea-8eaf-0ad3d9992c8c",
            "generation": 1,
        },
        "spec": {
            "application": "example",
            "config": {"version": 2, "host": "example.com", "namespace": "default", "annotations": {}},
            "image": "example/app",
        },
        "status": {
            "result": "SUCCEED",
            "observedGeneration": 1,
            "deployment_id": "deployment_id",
        },
    },
    "type": WatchEvent.MODIFIED,
}


class FakeCrdResourcesSyncer(object):
    @classmethod
    def update_crd_resources(cls):
        pass


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
        crd_watcher = CrdWatcher(spec_factory, deploy_queue, Configuration([]), lifecycle, FakeCrdResourcesSyncer)
        crd_watcher._watcher = watcher
        return crd_watcher

    @pytest.fixture
    def crd_resources_syncer(self):
        return FakeCrdResourcesSyncer()

    @pytest.fixture
    def crd_watcher_creation_disabled(self, spec_factory, deploy_queue, lifecycle, crd_resources_syncer, watcher):
        config = Configuration([])
        config.disable_crd_creation = True
        crd_watcher = CrdWatcher(spec_factory, deploy_queue, config, lifecycle, crd_resources_syncer)
        crd_watcher._watcher = watcher
        return crd_watcher

    @pytest.fixture(autouse=True)
    def status_get(self):
        with mock.patch("fiaas_deploy_daemon.crd.status.FiaasApplicationStatus.get", spec_set=True) as m:
            m.side_effect = NotFound
            yield m

    def test_does_not_update_crd_when_disabled(self, crd_watcher_creation_disabled, crd_resources_syncer):
        with mock.patch.object(crd_resources_syncer, "update_crd_resources") as m:
            crd_watcher_creation_disabled._watch(None)
            assert not m.called

    def test_updates_crd_resources_when_watching_it(self, crd_watcher):
        with mock.patch.object(FakeCrdResourcesSyncer, "update_crd_resources", return_value=None) as m:
            crd_watcher._watch(None)
            m.assert_called_once()

    def test_is_able_to_watch_custom_resource_definition(self, crd_watcher, deploy_queue, watcher):
        watcher.watch.return_value = [WatchEvent(ADD_EVENT, FiaasApplication)]

        assert deploy_queue.qsize() == 0
        crd_watcher._watch(None)
        assert deploy_queue.qsize() == 1

    @pytest.mark.parametrize(
        "event,deployer_event_type,annotations,repository",
        [
            (ADD_EVENT, "UPDATE", None, None),
            (ADD_EVENT, "UPDATE", {"deployment": {"fiaas/source-repository": "xyz"}}, "xyz"),
            (MODIFIED_EVENT, "UPDATE", None, None),
            (MODIFIED_EVENT, "UPDATE", {"deployment": {"fiaas/source-repository": "xyz"}}, "xyz"),
        ],
    )
    def test_deploy(
        self,
        crd_watcher,
        deploy_queue,
        spec_factory,
        watcher,
        app_spec,
        event,
        deployer_event_type,
        lifecycle,
        annotations,
        repository,
    ):
        event["object"]["spec"]["config"]["annotations"] = annotations
        watcher.watch.return_value = [WatchEvent(event, FiaasApplication)]

        spec = event["object"]["spec"]
        app_name = spec["application"]
        uid = event["object"]["metadata"]["uid"]
        namespace = event["object"]["metadata"]["namespace"]
        deployment_id = event["object"]["metadata"]["labels"]["fiaas/deployment_id"]

        app_spec = app_spec._replace(name=app_name, namespace=namespace, deployment_id=deployment_id)
        spec_factory.return_value = app_spec
        lifecycle_subject = Subject(
            uid, app_name, namespace, deployment_id, repository, app_spec.labels.status, app_spec.annotations.status
        )
        lifecycle.initiate.return_value = lifecycle_subject

        crd_watcher._watch(None)

        if event in [ADD_EVENT, MODIFIED_EVENT]:
            lifecycle.initiate.assert_called_once_with(
                uid=event["object"]["metadata"]["uid"],
                app_name=event["object"]["spec"]["application"],
                namespace=event["object"]["metadata"]["namespace"],
                deployment_id="deployment_id",
                repository=repository,
                labels=None,
                annotations=None,
            )

        app_config = spec["config"]
        additional_labels = AdditionalLabelsOrAnnotations()
        additional_annotations = AdditionalLabelsOrAnnotations()
        spec_factory.assert_called_once_with(
            uid="c1f34517-6f54-11ea-8eaf-0ad3d9992c8c",
            name=app_name,
            image=spec["image"],
            app_config=app_config,
            teams=[],
            tags=[],
            deployment_id=deployment_id,
            namespace=namespace,
            additional_labels=additional_labels,
            additional_annotations=additional_annotations,
        )

        assert deploy_queue.qsize() == 1
        deployer_event = deploy_queue.get_nowait()
        if event in [ADD_EVENT, MODIFIED_EVENT]:
            assert deployer_event == DeployerEvent(deployer_event_type, app_spec, lifecycle_subject)
        else:
            assert deployer_event == DeployerEvent(deployer_event_type, app_spec, None)
        assert deploy_queue.empty()

    def test_delete(self, crd_watcher, deploy_queue, watcher):
        watcher.watch.return_value = [WatchEvent(DELETED_EVENT, FiaasApplication)]

        crd_watcher._watch(None)

        assert deploy_queue.empty()

    @pytest.mark.parametrize("namespace", [None, "default"])
    def test_watch_namespace(self, crd_watcher, watcher, namespace):
        crd_watcher._watch(namespace)
        watcher.watch.assert_called_once_with(namespace=namespace)

    @pytest.mark.parametrize(
        "event,deployer_event_type,error,annotations,repository",
        [
            (ADD_EVENT, "UPDATE", YAMLError("invalid yaml"), {}, None),
            (ADD_EVENT, "UPDATE", InvalidConfiguration("invalid config"), {}, None),
            (MODIFIED_EVENT, "UPDATE", YAMLError("invalid yaml"), {}, None),
            (MODIFIED_EVENT, "UPDATE", InvalidConfiguration("invalid config"), {}, None),
            (
                MODIFIED_EVENT,
                "UPDATE",
                InvalidConfiguration("invalid config"),
                {"deployment": {"fiaas/source-repository": "xyz"}},
                "xyz",
            ),
        ],
    )
    def test_deploy_reports_failure_on_exception(
        self,
        crd_watcher,
        deploy_queue,
        spec_factory,
        watcher,
        event,
        deployer_event_type,
        error,
        lifecycle,
        annotations,
        repository,
    ):
        event["object"]["metadata"]["annotations"] = annotations
        watcher.watch.return_value = [WatchEvent(event, FiaasApplication)]

        spec_factory.side_effect = error

        lifecycle_subject = Subject(
            uid=event["object"]["metadata"]["uid"],
            app_name=event["object"]["spec"]["application"],
            namespace=event["object"]["metadata"]["namespace"],
            deployment_id="deployment_id",
            repository=repository,
            labels=None,
            annotations=None,
        )
        lifecycle.initiate.return_value = lifecycle_subject

        crd_watcher._watch(None)

        lifecycle.failed.assert_called_once_with(lifecycle_subject)
        assert deploy_queue.empty()

    @pytest.mark.parametrize(
        "result, count",
        (
            ("SUCCESS", 0),
            ("FAILED", 1),
            ("RUNNING", 1),
            ("INITIATED", 1),
            ("ANY_OTHER_VALUE_THAN_SUCCESS", 1),
        ),
    )
    def test_deploy_based_on_status_result(self, crd_watcher, deploy_queue, watcher, status_get, result, count):
        watcher.watch.return_value = [WatchEvent(ADD_EVENT, FiaasApplication)]
        status_get.side_effect = lambda *args, **kwargs: mock.DEFAULT  # disable default behavior of raising NotFound
        status_get.return_value = FiaasApplicationStatus(new=False, result=result)

        assert deploy_queue.qsize() == 0
        crd_watcher._watch(None)
        assert deploy_queue.qsize() == count

    def test_deploy_save_status(self, crd_watcher, deploy_queue, watcher, status_get):
        watcher.watch.return_value = [WatchEvent(STATUS_EVENT, FiaasApplication)]

        assert deploy_queue.qsize() == 0
        crd_watcher._watch(None)
        assert deploy_queue.qsize() == 0

    def test_deploy_skip_deleted_app(self, crd_watcher, deploy_queue, watcher, status_get):
        event = copy.deepcopy(MODIFIED_EVENT)
        event['object']['metadata']['deletionTimestamp'] = '2000-01-01T00:00:00Z'
        watcher.watch.return_value = [WatchEvent(event, FiaasApplication)]

        assert deploy_queue.qsize() == 0
        crd_watcher._watch(None)
        assert deploy_queue.qsize() == 0
