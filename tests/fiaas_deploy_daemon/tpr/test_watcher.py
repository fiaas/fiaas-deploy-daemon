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

class TestWatcher(object):
    def test_creates_third_party_resource_if_not_exists_when_watching_it(self, get, post):
        get.side_effect = NotFound("Something")

        watcher = Watcher(SpecFactory(Factory(), {}), Queue())
        watcher._watch()

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

    def test_is_able_to_watch_third_party_resource(self, get):
        response = Response()
        get.return_value = response

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

        watcher = Watcher(SpecFactory(Factory(), {}), Queue())

        assert watcher._deploy_queue.qsize() == 0
        watcher._watch()
        assert watcher._deploy_queue.qsize() == 1
