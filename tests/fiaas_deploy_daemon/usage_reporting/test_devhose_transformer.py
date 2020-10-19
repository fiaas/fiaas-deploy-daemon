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

from fiaas_deploy_daemon import Configuration
from fiaas_deploy_daemon.specs.models import LabelAndAnnotationSpec
from fiaas_deploy_daemon.usage_reporting import DevhoseDeploymentEventTransformer


class TestDevhoseDeploymentEventTransformer(object):
    @pytest.fixture()
    def config(self, request):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.environment = request.param.get("env")
        config.usage_reporting_cluster_name = 'cluster_name'
        config.usage_reporting_operator = 'operator_sdrn'
        config.usage_reporting_team = request.param.get("team")
        yield config

    @pytest.fixture()
    def transformer(self, config):
        transformer = DevhoseDeploymentEventTransformer(config)
        return transformer

    @pytest.mark.parametrize("statuses, timestamps, config, expected, annotations", [
        (["STARTED"], ["2018-09-10T13:49:05Z"], {"env": "dev"}, {
            "id": "test_app_deployment_id",
            "application": "testapp",
            "environment": "dev",
            "repository": "source/repo/name",
            "started_at": "2018-09-10T13:49:05Z",
            "timestamp": "2018-09-10T13:49:05Z",
            "target": {
                "infrastructure": "cluster_name",
                "provider": "cluster_name",
                "instance": "default",
                "team": "operator_sdrn"
            },
            "status": "in_progress",
            "source_type": "fiaas",
            "facility": "sdrn:schibsted:service:fiaas",
            "details": {"environment": "dev"},
            "trigger": DevhoseDeploymentEventTransformer.FIAAS_TRIGGER,
            "team": None
          }, {'fiaas/source-repository': 'source/repo/name'}),
        (["STARTED"], ["2018-09-10T13:49:05Z"], {"env": "pre"}, {
            "id": "test_app_deployment_id",
            "application": "testapp",
            "environment": "pre",
            "repository": "source/repo/name",
            "started_at": "2018-09-10T13:49:05Z",
            "timestamp": "2018-09-10T13:49:05Z",
            "target": {
                "infrastructure": "cluster_name",
                "provider": "cluster_name",
                "instance": "default",
                "team": "operator_sdrn"
            },
            "status": "in_progress",
            "source_type": "fiaas",
            "facility": "sdrn:schibsted:service:fiaas",
            "details": {"environment": "pre"},
            "trigger": DevhoseDeploymentEventTransformer.FIAAS_TRIGGER,
            "team": None
          }, {'fiaas/source-repository': 'source/repo/name'}),
        (["STARTED"], ["2018-09-10T13:49:05Z"], {"env": "pro"}, {
            "id": "test_app_deployment_id",
            "application": "testapp",
            "environment": "pro",
            "repository": "source/repo/name",
            "started_at": "2018-09-10T13:49:05Z",
            "timestamp": "2018-09-10T13:49:05Z",
            "target": {
                "infrastructure": "cluster_name",
                "provider": "cluster_name",
                "instance": "default",
                "team": "operator_sdrn"
            },
            "status": "in_progress",
            "source_type": "fiaas",
            "facility": "sdrn:schibsted:service:fiaas",
            "details": {"environment": "pro"},
            "trigger": DevhoseDeploymentEventTransformer.FIAAS_TRIGGER,
            "team": None
          }, {'fiaas/source-repository': 'source/repo/name'}),
        (["STARTED"], ["2018-09-10T13:49:05Z"], {"env": "something_else"}, {
            "id": "test_app_deployment_id",
            "application": "testapp",
            "environment": "other",
            "repository": "source/repo/name",
            "started_at": "2018-09-10T13:49:05Z",
            "timestamp": "2018-09-10T13:49:05Z",
            "target": {
                "infrastructure": "cluster_name",
                "provider": "cluster_name",
                "instance": "default",
                "team": "operator_sdrn"
            },
            "status": "in_progress",
            "source_type": "fiaas",
            "facility": "sdrn:schibsted:service:fiaas",
            "details": {"environment": "something_else"},
            "trigger": DevhoseDeploymentEventTransformer.FIAAS_TRIGGER,
            "team": None
          }, {'fiaas/source-repository': 'source/repo/name'}),
        (["STARTED", "SUCCESS"], ["2018-09-10T13:49:05Z", "2018-09-10T13:50:05Z"], {"env": "dev"}, {
            "id": "test_app_deployment_id",
            "application": "testapp",
            "environment": "dev",
            "repository": "source/repo/name",
            "started_at": "2018-09-10T13:49:05Z",
            "timestamp": "2018-09-10T13:50:05Z",
            "target": {
                "infrastructure": "cluster_name",
                "provider": "cluster_name",
                "instance": "default",
                "team": "operator_sdrn"
            },
            "status": "succeeded",
            "source_type": "fiaas",
            "facility": "sdrn:schibsted:service:fiaas",
            "details": {"environment": "dev"},
            "trigger": DevhoseDeploymentEventTransformer.FIAAS_TRIGGER,
            "team": None
          }, {'fiaas/source-repository': 'source/repo/name'}),
        (["STARTED", "FAILED"], ["2018-09-10T13:49:05Z", "2018-09-10T13:50:05Z"], {"env": "dev"}, {
            "id": "test_app_deployment_id",
            "application": "testapp",
            "environment": "dev",
            "repository": "source/repo/name",
            "started_at": "2018-09-10T13:49:05Z",
            "timestamp": "2018-09-10T13:50:05Z",
            "target": {
                "infrastructure": "cluster_name",
                "provider": "cluster_name",
                "instance": "default",
                "team": "operator_sdrn"
            },
            "status": "failed",
            "source_type": "fiaas",
            "facility": "sdrn:schibsted:service:fiaas",
            "details": {"environment": "dev"},
            "trigger": DevhoseDeploymentEventTransformer.FIAAS_TRIGGER,
            "team": None
          }, {'fiaas/source-repository': 'source/repo/name'}),
        (["STARTED"], ["2018-09-10T13:49:05Z"], {"env": "dev"}, {
            "id": "test_app_deployment_id",
            "application": "testapp",
            "environment": "dev",
            "repository": None,
            "started_at": "2018-09-10T13:49:05Z",
            "timestamp": "2018-09-10T13:49:05Z",
            "target": {
                "infrastructure": "cluster_name",
                "provider": "cluster_name",
                "instance": "default",
                "team": "operator_sdrn"
            },
            "status": "in_progress",
            "source_type": "fiaas",
            "facility": "sdrn:schibsted:service:fiaas",
            "details": {"environment": "dev"},
            "trigger": DevhoseDeploymentEventTransformer.FIAAS_TRIGGER,
            "team": None
        }, None),
        (["STARTED"], ["2018-09-10T13:49:05Z"], {"env": "dev", "team": "team_sdrn"}, {
            "id": "test_app_deployment_id",
            "application": "testapp",
            "environment": "dev",
            "repository": None,
            "started_at": "2018-09-10T13:49:05Z",
            "timestamp": "2018-09-10T13:49:05Z",
            "target": {
                "infrastructure": "cluster_name",
                "provider": "cluster_name",
                "instance": "default",
                "team": "operator_sdrn"
            },
            "status": "in_progress",
            "source_type": "fiaas",
            "facility": "sdrn:schibsted:service:fiaas",
            "details": {"environment": "dev"},
            "trigger": DevhoseDeploymentEventTransformer.FIAAS_TRIGGER,
            "team": "team_sdrn"
        }, None),
        (["FAILED"], ["2018-09-10T13:49:05Z"], {"env": "dev", "team": "team_sdrn"}, {
            "id": "test_app_deployment_id",
            "application": "testapp",
            "environment": "dev",
            "repository": None,
            "started_at": "2018-09-10T13:49:05Z",
            "timestamp": "2018-09-10T13:49:05Z",
            "target": {
                "infrastructure": "cluster_name",
                "provider": "cluster_name",
                "instance": "default",
                "team": "operator_sdrn"
            },
            "status": "failed",
            "source_type": "fiaas",
            "facility": "sdrn:schibsted:service:fiaas",
            "details": {"environment": "dev"},
            "trigger": DevhoseDeploymentEventTransformer.FIAAS_TRIGGER,
            "team": "team_sdrn"
        }, None),
    ], indirect=['config'])
    def test_transformation(self, transformer, app_spec, statuses, timestamps, expected, annotations):
        if annotations:
            app_spec = app_spec._replace(annotations=LabelAndAnnotationSpec(*[annotations] * 7))
        with mock.patch("fiaas_deploy_daemon.usage_reporting.transformer._timestamp") as timestamp:
            timestamp.side_effect = timestamps
            for status in statuses:
                transformed = transformer(status, app_spec.name, app_spec.namespace, app_spec.deployment_id,
                                          _repository(app_spec))
            assert expected == transformed


def _repository(app_spec):
    return app_spec.annotations.deployment.get("fiaas/source-repository") if app_spec.annotations.deployment else None
