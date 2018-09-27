#!/usr/bin/env python
# -*- coding: utf-8
import json

import pytest
import mock

from fiaas_deploy_daemon import Configuration
from fiaas_deploy_daemon.specs.models import LabelAndAnnotationSpec
from fiaas_deploy_daemon.tracking import DevhoseDeploymentEventTransformer


class TestDevhoseDeploymentEventTransformer(object):
    @pytest.fixture()
    def config(self, request):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.environment = request.param
        config.tracking_cluster_name = 'cluster_name'
        config.tracking_provider_identifier = 'team_sdrn'
        yield config

    @pytest.fixture()
    def transformer(self, config):
        transformer = DevhoseDeploymentEventTransformer(config)
        return transformer

    @pytest.mark.parametrize("statuses, timestamps, config, expected, annotations", [
        (["STARTED"], ["2018-09-10T13:49:05"], "dev", {
            "id": "test_app_deployment_id",
            "application": "testapp",
            "environment": "dev",
            "repository": "http://source/repo/path",
            "started_at": "2018-09-10T13:49:05",
            "timestamp": "2018-09-10T13:49:05",
            "target": {"infrastructure": "cluster_name", "provider": "team_sdrn", "instance": "default"},
            "status": "in_progress",
            "source_type": "fiaas",
            "facility": "sdrn:schibsted:service:fiaas",
            "details": {"environment": "dev"}
          }, {'pipeline.schibsted.io/repoName': 'http://source/repo/path'}),
        (["STARTED"], ["2018-09-10T13:49:05"], "pre", {
            "id": "test_app_deployment_id",
            "application": "testapp",
            "environment": "pre",
            "repository": "http://source/repo/path",
            "started_at": "2018-09-10T13:49:05",
            "timestamp": "2018-09-10T13:49:05",
            "target": {"infrastructure": "cluster_name", "provider": "team_sdrn", "instance": "default"},
            "status": "in_progress",
            "source_type": "fiaas",
            "facility": "sdrn:schibsted:service:fiaas",
            "details": {"environment": "pre"}
          }, {'pipeline.schibsted.io/repoName': 'http://source/repo/path'}),
        (["STARTED"], ["2018-09-10T13:49:05"], "pro", {
            "id": "test_app_deployment_id",
            "application": "testapp",
            "environment": "pro",
            "repository": "http://source/repo/path",
            "started_at": "2018-09-10T13:49:05",
            "timestamp": "2018-09-10T13:49:05",
            "target": {"infrastructure": "cluster_name", "provider": "team_sdrn", "instance": "default"},
            "status": "in_progress",
            "source_type": "fiaas",
            "facility": "sdrn:schibsted:service:fiaas",
            "details": {"environment": "pro"}
          }, {'pipeline.schibsted.io/repoName': 'http://source/repo/path'}),
        (["STARTED"], ["2018-09-10T13:49:05"], "something_else", {
            "id": "test_app_deployment_id",
            "application": "testapp",
            "environment": "other",
            "repository": "http://source/repo/path",
            "started_at": "2018-09-10T13:49:05",
            "timestamp": "2018-09-10T13:49:05",
            "target": {"infrastructure": "cluster_name", "provider": "team_sdrn", "instance": "default"},
            "status": "in_progress",
            "source_type": "fiaas",
            "facility": "sdrn:schibsted:service:fiaas",
            "details": {"environment": "something_else"}
          }, {'pipeline.schibsted.io/repoName': 'http://source/repo/path'}),
        (["STARTED", "SUCCESS"], ["2018-09-10T13:49:05", "2018-09-10T13:50:05"], "dev", {
            "id": "test_app_deployment_id",
            "application": "testapp",
            "environment": "dev",
            "repository": "http://source/repo/path",
            "started_at": "2018-09-10T13:49:05",
            "timestamp": "2018-09-10T13:50:05",
            "target": {"infrastructure": "cluster_name", "provider": "team_sdrn", "instance": "default"},
            "status": "succeeded",
            "source_type": "fiaas",
            "facility": "sdrn:schibsted:service:fiaas",
            "details": {"environment": "dev"}
        }, {'pipeline.schibsted.io/repoName': 'http://source/repo/path'}),
        (["STARTED", "FAILED"], ["2018-09-10T13:49:05", "2018-09-10T13:50:05"], "dev", {
            "id": "test_app_deployment_id",
            "application": "testapp",
            "environment": "dev",
            "repository": "http://source/repo/path",
            "started_at": "2018-09-10T13:49:05",
            "timestamp": "2018-09-10T13:50:05",
            "target": {"infrastructure": "cluster_name", "provider": "team_sdrn", "instance": "default"},
            "status": "failed",
            "source_type": "fiaas",
            "facility": "sdrn:schibsted:service:fiaas",
            "details": {"environment": "dev"}
        }, {'pipeline.schibsted.io/repoName': 'http://source/repo/path'}),
        (["STARTED"], ["2018-09-10T13:49:05"], "dev", {
            "id": "test_app_deployment_id",
            "application": "testapp",
            "environment": "dev",
            "repository": None,
            "started_at": "2018-09-10T13:49:05",
            "timestamp": "2018-09-10T13:49:05",
            "target": {"infrastructure": "cluster_name", "provider": "team_sdrn", "instance": "default"},
            "status": "in_progress",
            "source_type": "fiaas",
            "facility": "sdrn:schibsted:service:fiaas",
            "details": {"environment": "dev"}
        }, None),
    ], indirect=['config'])
    def test_transformation(self, transformer, app_spec, statuses, timestamps, expected, annotations):
        if annotations:
            app_spec = app_spec._replace(annotations=LabelAndAnnotationSpec(*[annotations] * 5))
        with mock.patch("fiaas_deploy_daemon.tracking.transformer._timestamp") as timestamp:
            timestamp.side_effect = timestamps
            for status in statuses:
                transformed = json.loads(transformer(status, app_spec))
            assert expected == transformed
