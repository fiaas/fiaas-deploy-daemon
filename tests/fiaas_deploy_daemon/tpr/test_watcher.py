#!/usr/bin/env python
# -*- coding: utf-8
import json
from Queue import Queue

from k8s.client import NotFound
from mock import mock, Mock
from requests import Response

from fiaas_deploy_daemon.specs import SpecFactory
from fiaas_deploy_daemon.specs.v2 import Factory
from fiaas_deploy_daemon.tpr import Watcher


def given_third_party_resource_does_not_exist(mock_get):
    mock_get.side_effect = NotFound("Something")


def when_watching_the_third_party_resource():
    watcher = Watcher(SpecFactory(Factory(), {}), Queue())
    watcher._watch()


def then_the_third_party_resource_should_be_created(mock_post):
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
    assert mock_post.call_args_list == calls


class TestWatcher(object):
    def test_creates_third_party_resource_if_not_exists_when_watching_it(self):
        with mock.patch('k8s.client.Client.get') as mock_get, \
                mock.patch('k8s.client.Client.post') as mock_post:
            given_third_party_resource_does_not_exist(mock_get)
            when_watching_the_third_party_resource()
            then_the_third_party_resource_should_be_created(mock_post)

    def test_is_able_to_watch_third_party_resource(self):
        response = Response()
        event = {
            'object': {
                'metadata': {
                    'labels': {
                        'fiaas/deployment_id': 'deployment_id'
                    },
                    'name': 'example',
                    'namespace': 'default'
                },
                'spec': {
                    'application': 'example',
                    'config': {
                        'version': 2,
                        'host': 'example.com',
                        'namespace': 'default'
                    },
                    'image': 'example/app'
                }
            },
            'type': 'ADDED'
        }
        response.iter_content = Mock(return_value=[json.dumps(event)])
        response.status_code = Mock(return_value=200)
        with mock.patch('k8s.client.Client.get', return_value=response):
            watcher = Watcher(SpecFactory(Factory(), {}), Queue())

            assert watcher._deploy_queue.qsize() == 0
            watcher._watch()
            assert watcher._deploy_queue.qsize() == 1
