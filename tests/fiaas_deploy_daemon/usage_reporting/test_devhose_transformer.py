#!/usr/bin/env python
# -*- coding: utf-8

import mock
import pytest

from fiaas_deploy_daemon import Configuration
from fiaas_deploy_daemon.specs.models import LabelAndAnnotationSpec
from fiaas_deploy_daemon.usage_reporting import DevhoseDeploymentEventTransformer


class TestDevhoseDeploymentEventTransformer(object):
    @pytest.fixture()
    def config(self, request):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.environment = request.param
        config.usage_reporting_cluster_name = 'cluster_name'
        config.usage_reporting_provider_identifier = 'team_sdrn'
        yield config

    @pytest.fixture()
    def transformer(self, config):
        transformer = DevhoseDeploymentEventTransformer(config)
        return transformer

    @pytest.mark.parametrize("statuses, timestamps, config, expected, annotations", [
        (["STARTED"], ["2018-09-10T13:49:05Z"], "dev", {
            "id": "test_app_deployment_id",
            "application": "testapp",
            "environment": "dev",
            "repository": "source/repo/name",
            "started_at": "2018-09-10T13:49:05Z",
            "timestamp": "2018-09-10T13:49:05Z",
            "target": {"infrastructure": "cluster_name", "provider": "team_sdrn", "instance": "default"},
            "status": "in_progress",
            "source_type": "fiaas",
            "facility": "sdrn:schibsted:service:fiaas",
            "details": {"environment": "dev"},
            "trigger": DevhoseDeploymentEventTransformer.FIAAS_TRIGGER,
          }, {'fiaas/source-repository': 'source/repo/name'}),
        (["STARTED"], ["2018-09-10T13:49:05Z"], "pre", {
            "id": "test_app_deployment_id",
            "application": "testapp",
            "environment": "pre",
            "repository": "source/repo/name",
            "started_at": "2018-09-10T13:49:05Z",
            "timestamp": "2018-09-10T13:49:05Z",
            "target": {"infrastructure": "cluster_name", "provider": "team_sdrn", "instance": "default"},
            "status": "in_progress",
            "source_type": "fiaas",
            "facility": "sdrn:schibsted:service:fiaas",
            "details": {"environment": "pre"},
            "trigger": DevhoseDeploymentEventTransformer.FIAAS_TRIGGER,
          }, {'fiaas/source-repository': 'source/repo/name'}),
        (["STARTED"], ["2018-09-10T13:49:05Z"], "pro", {
            "id": "test_app_deployment_id",
            "application": "testapp",
            "environment": "pro",
            "repository": "source/repo/name",
            "started_at": "2018-09-10T13:49:05Z",
            "timestamp": "2018-09-10T13:49:05Z",
            "target": {"infrastructure": "cluster_name", "provider": "team_sdrn", "instance": "default"},
            "status": "in_progress",
            "source_type": "fiaas",
            "facility": "sdrn:schibsted:service:fiaas",
            "details": {"environment": "pro"},
            "trigger": DevhoseDeploymentEventTransformer.FIAAS_TRIGGER,
          }, {'fiaas/source-repository': 'source/repo/name'}),
        (["STARTED"], ["2018-09-10T13:49:05Z"], "something_else", {
            "id": "test_app_deployment_id",
            "application": "testapp",
            "environment": "other",
            "repository": "source/repo/name",
            "started_at": "2018-09-10T13:49:05Z",
            "timestamp": "2018-09-10T13:49:05Z",
            "target": {"infrastructure": "cluster_name", "provider": "team_sdrn", "instance": "default"},
            "status": "in_progress",
            "source_type": "fiaas",
            "facility": "sdrn:schibsted:service:fiaas",
            "details": {"environment": "something_else"},
            "trigger": DevhoseDeploymentEventTransformer.FIAAS_TRIGGER,
          }, {'fiaas/source-repository': 'source/repo/name'}),
        (["STARTED", "SUCCESS"], ["2018-09-10T13:49:05Z", "2018-09-10T13:50:05Z"], "dev", {
            "id": "test_app_deployment_id",
            "application": "testapp",
            "environment": "dev",
            "repository": "source/repo/name",
            "started_at": "2018-09-10T13:49:05Z",
            "timestamp": "2018-09-10T13:50:05Z",
            "target": {"infrastructure": "cluster_name", "provider": "team_sdrn", "instance": "default"},
            "status": "succeeded",
            "source_type": "fiaas",
            "facility": "sdrn:schibsted:service:fiaas",
            "details": {"environment": "dev"},
            "trigger": DevhoseDeploymentEventTransformer.FIAAS_TRIGGER,
          }, {'fiaas/source-repository': 'source/repo/name'}),
        (["STARTED", "FAILED"], ["2018-09-10T13:49:05Z", "2018-09-10T13:50:05Z"], "dev", {
            "id": "test_app_deployment_id",
            "application": "testapp",
            "environment": "dev",
            "repository": "source/repo/name",
            "started_at": "2018-09-10T13:49:05Z",
            "timestamp": "2018-09-10T13:50:05Z",
            "target": {"infrastructure": "cluster_name", "provider": "team_sdrn", "instance": "default"},
            "status": "failed",
            "source_type": "fiaas",
            "facility": "sdrn:schibsted:service:fiaas",
            "details": {"environment": "dev"},
            "trigger": DevhoseDeploymentEventTransformer.FIAAS_TRIGGER,
          }, {'fiaas/source-repository': 'source/repo/name'}),
        (["STARTED"], ["2018-09-10T13:49:05Z"], "dev", {
            "id": "test_app_deployment_id",
            "application": "testapp",
            "environment": "dev",
            "repository": None,
            "started_at": "2018-09-10T13:49:05Z",
            "timestamp": "2018-09-10T13:49:05Z",
            "target": {"infrastructure": "cluster_name", "provider": "team_sdrn", "instance": "default"},
            "status": "in_progress",
            "source_type": "fiaas",
            "facility": "sdrn:schibsted:service:fiaas",
            "details": {"environment": "dev"},
            "trigger": DevhoseDeploymentEventTransformer.FIAAS_TRIGGER,
        }, None),
    ], indirect=['config'])
    def test_transformation(self, transformer, app_spec, statuses, timestamps, expected, annotations):
        if annotations:
            app_spec = app_spec._replace(annotations=LabelAndAnnotationSpec(*[annotations] * 5))
        with mock.patch("fiaas_deploy_daemon.usage_reporting.transformer._timestamp") as timestamp:
            timestamp.side_effect = timestamps
            for status in statuses:
                transformed = transformer(status, app_spec)
            assert expected == transformed
