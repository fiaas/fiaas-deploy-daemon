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

import mock
import pytest
from monotonic import monotonic as time_monotonic

from fiaas_deploy_daemon.deployer.bookkeeper import Bookkeeper
from fiaas_deploy_daemon.config import Configuration
from fiaas_deploy_daemon.deployer.kubernetes.ready_check import ReadyCheck
from fiaas_deploy_daemon.lifecycle import Lifecycle, Subject
from fiaas_deploy_daemon.specs.models import LabelAndAnnotationSpec

REPLICAS = 2


class TestReadyCheck(object):
    @pytest.fixture
    def bookkeeper(self):
        return mock.create_autospec(Bookkeeper, spec_set=True)

    @pytest.fixture
    def lifecycle(self):
        return mock.create_autospec(Lifecycle, spec_set=True)

    @pytest.fixture
    def lifecycle_subject(self, app_spec):
        return Subject(app_spec.uid, app_spec.name, app_spec.namespace, app_spec.deployment_id, None,
                       app_spec.labels.status, app_spec.annotations.status)

    @pytest.fixture
    def config(self):
        return Configuration([])

    @pytest.mark.parametrize("generation,observed_generation", (
            (0, 0),
            (0, 1)
    ))
    def test_deployment_complete(self, get, app_spec, bookkeeper, generation, observed_generation, lifecycle,
                                 lifecycle_subject, config):
        self._create_response(get, generation=generation, observed_generation=observed_generation)
        ready = ReadyCheck(app_spec, bookkeeper, lifecycle, lifecycle_subject, config)

        assert ready() is False
        bookkeeper.success.assert_called_with(app_spec)
        bookkeeper.failed.assert_not_called()
        lifecycle.success.assert_called_with(lifecycle_subject)
        lifecycle.failed.assert_not_called()

    @pytest.mark.parametrize("requested,replicas,available,updated,generation,observed_generation", (
            (8, 9, 7, 2, 0, 0),
            (2, 2, 1, 2, 0, 0),
            (2, 2, 2, 1, 0, 0),
            (2, 1, 1, 1, 0, 0),
            (1, 2, 1, 1, 0, 0),
            (2, 2, 2, 2, 1, 0),
    ))
    def test_deployment_incomplete(self, get, app_spec, bookkeeper, requested, replicas, available, updated,
                                   generation, observed_generation, lifecycle, lifecycle_subject, config):
        self._create_response(get, requested, replicas, available, updated, generation, observed_generation)
        ready = ReadyCheck(app_spec, bookkeeper, lifecycle, lifecycle_subject, config)

        assert ready() is True
        bookkeeper.success.assert_not_called()
        bookkeeper.failed.assert_not_called()
        lifecycle.success.assert_not_called()
        lifecycle.failed.assert_not_called()

    @pytest.mark.parametrize("requested,replicas,available,updated,annotations,repository", (
            (8, 9, 7, 2, None, None),
            (2, 2, 1, 2, None, None),
            (2, 2, 2, 1, None, None),
            (2, 1, 1, 1, None, None),
            (2, 1, 1, 1, {"fiaas/source-repository": "xyz"}, "xyz"),
    ))
    def test_deployment_failed(self, get, app_spec, bookkeeper, requested, replicas, available, updated,
                               lifecycle, lifecycle_subject, annotations, repository, config):
        if annotations:
            app_spec = app_spec._replace(annotations=LabelAndAnnotationSpec(*[annotations] * 6))

        self._create_response(get, requested, replicas, available, updated)

        ready = ReadyCheck(app_spec, bookkeeper, lifecycle, lifecycle_subject, config)
        ready._fail_after = time_monotonic()

        assert ready() is False
        bookkeeper.success.assert_not_called()
        bookkeeper.failed.assert_called_with(app_spec)
        lifecycle.success.assert_not_called()
        lifecycle.failed.assert_called_with(lifecycle_subject)

    def test_deployment_complete_deactivated(self, get, app_spec, bookkeeper, lifecycle, lifecycle_subject, config):

        self._create_response_zero_replicas(get)
        ready = ReadyCheck(app_spec, bookkeeper, lifecycle, lifecycle_subject, config)

        assert ready() is False
        bookkeeper.success.assert_called_with(app_spec)
        bookkeeper.failed.assert_not_called()
        lifecycle.success.assert_called_with(lifecycle_subject)
        lifecycle.failed.assert_not_called()

    @staticmethod
    def _create_response(get, requested=REPLICAS, replicas=REPLICAS, available=REPLICAS, updated=REPLICAS,
                         generation=0, observed_generation=0):
        get.side_effect = None
        resp = mock.MagicMock()
        get.return_value = resp
        resp.json.return_value = {
            'metadata': pytest.helpers.create_metadata('testapp', generation=generation),
            'spec': {
                'selector': {'matchLabels': {'app': 'testapp'}},
                'template': {
                    'spec': {
                        'containers': [{
                            'name': 'testapp',
                            'image': 'finntech/testimage:version',
                        }]
                    },
                    'metadata': pytest.helpers.create_metadata('testapp')
                },
                'replicas': requested
            },
            'status': {
                'replicas': replicas,
                'availableReplicas': available,
                'unavailableReplicas': replicas - available,
                'updatedReplicas': updated,
                'observedGeneration': observed_generation,
            }
        }

    @staticmethod
    def _create_response_zero_replicas(get):
        get.side_effect = None
        resp = mock.MagicMock()
        get.return_value = resp
        resp.json.return_value = {
            'metadata': pytest.helpers.create_metadata('testapp', generation=0),
            'spec': {
                'selector': {'matchLabels': {'app': 'testapp'}},
                'template': {
                    'spec': {
                        'containers': [{
                            'name': 'testapp',
                            'image': 'finntech/testimage:version',
                        }]
                    },
                    'metadata': pytest.helpers.create_metadata('testapp')
                },
                'replicas': 0
            },
            'status': {
                'observedGeneration': 0,
            }
        }
