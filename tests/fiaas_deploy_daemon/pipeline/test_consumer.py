#!/usr/bin/env python
# -*- coding: utf-8
import json
from Queue import Queue, Empty
from collections import namedtuple
from copy import deepcopy

import kafka
import pytest
from mock import create_autospec

from fiaas_deploy_daemon import config
from fiaas_deploy_daemon.pipeline import consumer
from fiaas_deploy_daemon.pipeline.reporter import Reporter
from fiaas_deploy_daemon.specs import models
from fiaas_deploy_daemon.specs.factory import SpecFactory

DummyMessage = namedtuple("DummyMessage", ("value",))
EVENT = {
    u'action': u'deploy',
    u'artifact_url': u'http://www.test/tp-api_2.11-201601050306-SNAPSHOT.war',
    u'artifacts_by_type': {
        u'': u'http://www.test/tp-api_2.11-201601050306-SNAPSHOT.war',
        u'docker': u'finntech/tp-api:1452002819',
        u'fiaas': u'http://www.test/tp-api_2.11-201601050306-SNAPSHOT-fiaas.yml'
    },
    u'callback_url': u'http://www.test/deployment/artifact/304201',
    u'environment': u'prod',
    u'project_name': u'tp-api',
    u'puppet_name': u'tp-api',
    u'timestamp': u'2016-01-05T15:20:26+01:00',
    u'user': u'fikameva'
}
MESSAGE = DummyMessage(json.dumps(EVENT))
APP_SPEC = models.AppSpec(None, u"tp-api", u'finntech/tp-api:1452002819', None, 1, None, None, None)
APP_SPEC_TRAVEL = models.AppSpec(None, u"travel-lms-web", u'finntech/tp-api:1452002819', None, 1, None, None, None)


class TestConsumer(object):
    def setup(self):
        self.deploy_queue = Queue()
        self.config = _FakeConfig()
        self.mock_reporter = create_autospec(Reporter, instance=True)
        self.mock_factory = create_autospec(SpecFactory, instance=True)
        self.mock_factory.return_value = APP_SPEC
        self.consumer = consumer.Consumer(self.deploy_queue, self.config, self.mock_reporter, self.mock_factory)
        self.mock_consumer = create_autospec(kafka.KafkaConsumer, instance=True)
        self.consumer._consumer = self.mock_consumer

    def test_fail_on_missing_config(self):
        with pytest.raises(config.InvalidConfigurationException) as e:
            self.consumer._connect_kafka()

        assert e.value.message == "FakeConfig"

    def test_create_spec_from_event(self):
        self.consumer._create_spec(EVENT)

        assert self.mock_factory.called
        assert self.mock_factory.call_count == 1

    def test_fail_if_no_docker_image(self):
        event = deepcopy(EVENT)
        del event[u"artifacts_by_type"][u"docker"]

        with pytest.raises(consumer.NoDockerArtifactException):
            self.consumer._create_spec(event)

    def test_fail_if_no_fiaas_config(self):
        event = deepcopy(EVENT)
        del event[u"artifacts_by_type"][u"fiaas"]

        with pytest.raises(consumer.NoFiaasArtifactException):
            self.consumer._create_spec(event)

    def test_deserialize_kafka_message(self):
        event = self.consumer._deserialize(MESSAGE)

        assert event == EVENT

    def test_consume_message_in_correct_cluster(self):
        self.mock_consumer.__iter__.return_value = [MESSAGE]

        self.consumer()

        app_spec = self.deploy_queue.get_nowait()
        assert app_spec is APP_SPEC

    def test_skip_message_if_wrong_cluster(self, monkeypatch):
        self.mock_consumer.__iter__.return_value = [MESSAGE]
        monkeypatch.setattr(self.consumer, "_environment", "dev")

        self.consumer()

        with pytest.raises(Empty):
            self.deploy_queue.get_nowait()

    def test_registers_callback(self):
        self.mock_consumer.__iter__.return_value = [MESSAGE]

        self.consumer()

        self.mock_reporter.register.assert_called_with(APP_SPEC.image, EVENT[u"callback_url"])

    def test_should_not_deploy_apps_to_gke_prod_not_in_whitelist(self, monkeypatch):
        self.mock_consumer.__iter__.return_value = [MESSAGE]
        monkeypatch.setattr(self.consumer._config, "infrastructure", "gke")

        with pytest.raises(consumer.NotWhiteListeApplicationException):
            self.consumer()

    def test_should_deploy_apps_to_gke_prod_in_whitelist(self, monkeypatch):
        self.mock_consumer.__iter__.return_value = [MESSAGE]
        monkeypatch.setattr(self.consumer._config, "infrastructure", "gke")
        self.mock_factory.return_value = APP_SPEC_TRAVEL
        self.consumer()
        app_spec = self.deploy_queue.get_nowait()
        assert app_spec is APP_SPEC_TRAVEL

    @pytest.mark.parametrize("target_cluster", ("prod", "prod1", "prod2", "prod999"))
    def test_set_correct_environment(self, target_cluster):
        config = _FakeConfig(cluster=target_cluster)
        env = consumer.Consumer._extract_env(config)

        assert env == "prod"


class _FakeConfig(object):
    def __init__(self, cluster="prod", infrastructure="diy"):
        self.target_cluster = cluster
        self.infrastructure = infrastructure

    def resolve_service(self, service):
        raise config.InvalidConfigurationException("FakeConfig")


def _make_env_message(template, env):
    message = deepcopy(template)
    message[u"environment"] = env
    return message
