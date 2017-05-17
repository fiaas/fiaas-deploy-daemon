#!/usr/bin/env python
# -*- coding: utf-8

from Queue import Queue

from mock import mock

from fiaas_deploy_daemon.specs import SpecFactory
from fiaas_deploy_daemon.tpr import Watcher
from k8s.client import NotFound


class TestWatcher(object):
    def given_third_party_resource_does_not_exist(self):
        self.mock_get.side_effect = NotFound("Something")

    def when_watching_the_third_party_resource(self):
        self.watcher = Watcher(SpecFactory([]), Queue())
        self.watcher._watch()

    def then_the_third_party_resource_should_be_created(self):
        self.mock_post.assert_called_once_with(
            "/apis/extensions/v1beta1/thirdpartyresources/",
            {
                'metadata': {'namespace': 'default', 'name': 'paasbeta-application.schibsted.io'},
                'description': 'A paas application definition',
                'versions': [{'name': 'v1beta'}]
            }
        )

    def test_creates_third_party_resource_if_not_exists_when_tryi(self):
        with mock.patch('k8s.client.Client.get') as self.mock_get, \
                mock.patch('k8s.client.Client.post') as self.mock_post:
            self.given_third_party_resource_does_not_exist()
            self.when_watching_the_third_party_resource()
            self.then_the_third_party_resource_should_be_created()
