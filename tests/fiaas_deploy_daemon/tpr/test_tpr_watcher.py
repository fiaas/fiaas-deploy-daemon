#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import, unicode_literals

from Queue import Queue

import mock
import pytest
from k8s.base import WatchEvent
from k8s.client import NotFound
from k8s.watcher import Watcher

from fiaas_deploy_daemon.deployer import DeployerEvent
from fiaas_deploy_daemon.specs.models import AppSpec
from fiaas_deploy_daemon.tpr import TprWatcher
from fiaas_deploy_daemon.tpr.types import PaasbetaApplication

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


class TestTprWatcher(object):

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
    def tpr_watcher(self, spec_factory, deploy_queue, watcher):
        mock_watcher = TprWatcher(spec_factory, deploy_queue)
        mock_watcher._watcher = watcher
        return mock_watcher

    def test_creates_third_party_resource_if_not_exists_when_watching_it(self, get, post, tpr_watcher, watcher):
        get.side_effect = NotFound("Something")
        watcher.watch.side_effect = NotFound("Something")

        tpr_watcher._watch()

        calls = [
            mock.call("/apis/extensions/v1beta1/thirdpartyresources/", {
                'metadata': {'namespace': 'default', 'name': 'paasbeta-application.schibsted.io'},
                'description': 'A paas application definition',
                'versions': [{'name': 'v1beta'}]
            }),
            mock.call("/apis/extensions/v1beta1/thirdpartyresources/", {
                'metadata': {'namespace': 'default', 'name': 'paasbeta-status.schibsted.io'},
                'description': 'A paas application status',
                'versions': [{'name': 'v1beta'}]
            })
        ]
        assert post.call_args_list == calls

    def test_is_able_to_watch_third_party_resource(self, tpr_watcher, deploy_queue, watcher):
        watcher.watch.return_value = [WatchEvent(ADD_EVENT, PaasbetaApplication)]

        assert deploy_queue.qsize() == 0
        tpr_watcher._watch()
        assert deploy_queue.qsize() == 1

    @pytest.mark.parametrize("event,deployer_event_type", [
        (ADD_EVENT, "UPDATE"),
        (MODIFIED_EVENT, "UPDATE"),
        (DELETED_EVENT, "DELETE"),
    ])
    def test_deploy(self, tpr_watcher, deploy_queue, spec_factory, watcher, event, deployer_event_type):
        watcher.watch.return_value = [WatchEvent(event, PaasbetaApplication)]

        app_spec = mock.create_autospec(AppSpec, instance=True, set_spec=True)
        spec_factory.return_value = app_spec

        tpr_watcher._watch()

        spec = event["object"]["spec"]
        event_deployment_id = event["object"]["metadata"]["labels"]["fiaas/deployment_id"]
        deployment_id = event_deployment_id if deployer_event_type != "DELETE" else None
        app_config = spec["config"]
        spec_factory.assert_called_once_with(name=spec["application"], image=spec["image"], app_config=app_config,
                                             teams=[], tags=[],
                                             deployment_id=deployment_id,
                                             namespace=event["object"]["metadata"]["namespace"])

        assert deploy_queue.qsize() == 1
        deployer_event = deploy_queue.get_nowait()
        assert deployer_event == DeployerEvent(deployer_event_type, app_spec)
        assert deploy_queue.empty()
