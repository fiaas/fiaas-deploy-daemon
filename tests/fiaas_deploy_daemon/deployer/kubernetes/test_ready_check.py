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
from k8s.models.deployment import Deployment
from monotonic import monotonic as time_monotonic

from fiaas_deploy_daemon.deployer.bookkeeper import Bookkeeper
from fiaas_deploy_daemon.deployer.kubernetes.ready_check import ReadyCheck
from fiaas_deploy_daemon.lifecycle import Lifecycle
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
    def deployment(self):
        with mock.patch("k8s.models.deployment.Deployment.get") as m:
            deployment = mock.create_autospec(Deployment(), spec_set=True)
            deployment.spec.replicas.return_value = REPLICAS
            m.return_value = deployment
            return deployment

    @pytest.mark.parametrize("generation,observedGeneration", (
            (0, 0),
            (0, 1)
    ))
    def test_deployment_complete(self, get, app_spec, bookkeeper, generation, observedGeneration, lifecycle):
        self._create_response(get, generation=generation, observedGeneration=observedGeneration)

        ready = ReadyCheck(app_spec, bookkeeper, lifecycle)

        assert ready() is False
        bookkeeper.success.assert_called_with(app_spec)
        bookkeeper.failed.assert_not_called()

    @pytest.mark.parametrize("requested,replicas,available,updated,generation,observedGeneration", (
            (8, 9, 7, 2, 0, 0),
            (2, 2, 1, 2, 0, 0),
            (2, 2, 2, 1, 0, 0),
            (2, 1, 1, 1, 0, 0),
            (1, 2, 1, 1, 0, 0),
            (2, 2, 2, 2, 1, 0),
    ))
    def test_deployment_incomplete(self, get, app_spec, bookkeeper, requested, replicas, available, updated,
                                   generation, observedGeneration, lifecycle):
        self._create_response(get, requested, replicas, available, updated, generation, observedGeneration)

        ready = ReadyCheck(app_spec, bookkeeper, lifecycle)

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
                               lifecycle, annotations, repository):
        if annotations:
            app_spec = app_spec._replace(annotations=LabelAndAnnotationSpec(*[annotations] * 6))

        self._create_response(get, requested, replicas, available, updated)

        ready = ReadyCheck(app_spec, bookkeeper, lifecycle)
        ready._fail_after = time_monotonic()

        assert ready() is False
        bookkeeper.success.assert_not_called()
        bookkeeper.failed.assert_called_with(app_spec)
        lifecycle.success.assert_not_called()
        lifecycle.failed.assert_called_with(app_name=app_spec.name, namespace=app_spec.namespace,
                                            deployment_id=app_spec.deployment_id, repository=repository,
                                            labels=app_spec.labels.status, annotations=app_spec.annotations.status)

    @staticmethod
    def _create_response(get, requested=REPLICAS, replicas=REPLICAS, available=REPLICAS, updated=REPLICAS, generation=0, observedGeneration=0):
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
                'observedGeneration': observedGeneration,
            }
        }
