#!/usr/bin/env python
# -*- coding: utf-8

from Queue import Queue

from mock import mock

from fiaas_deploy_daemon.specs import SpecFactory
from fiaas_deploy_daemon.tpr import Watcher
from k8s.client import NotFound


def given_third_party_resource_does_not_exist(mock_get):
    mock_get.side_effect = NotFound("Something")


def when_watching_the_third_party_resource():
    watcher = Watcher(SpecFactory([]), Queue())
    watcher._watch()


def then_the_third_party_resource_should_be_created(mock_post):
    mock_post.assert_called_once_with(
        "/apis/extensions/v1beta1/thirdpartyresources/",
        {
            'metadata': {'namespace': 'default', 'name': 'paasbeta-application.schibsted.io'},
            'description': 'A paas application definition',
            'versions': [{'name': 'v1beta'}]
        }
    )


class TestWatcher(object):
    def test_creates_third_party_resource_if_not_exists_when_tryi(self):
        with mock.patch('k8s.client.Client.get') as mock_get, \
                mock.patch('k8s.client.Client.post') as mock_post:
            given_third_party_resource_does_not_exist(mock_get)
            when_watching_the_third_party_resource()
            then_the_third_party_resource_should_be_created(mock_post)
