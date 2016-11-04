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
from fiaas_deploy_daemon.pipeline import consumer as pipeline_consumer
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
    u'teams': u'IO',
    u'tags': u'cloud',
    u'timestamp': u'2016-01-05T15:20:26+01:00',
    u'user': u'fikameva'
}
MESSAGE = DummyMessage(json.dumps(EVENT))
APP_SPEC = models.AppSpec(None, u"tp-api", u'finntech/tp-api:1452002819', 1, None, None, None, None, None, None, None, None, None)
APP_SPEC_TRAVEL = models.AppSpec(None, u"travel-lms-web", u'finntech/tp-api:1452002819', 1,
                                 None, None, None, None, None, None, None, None, None)


class TestConsumer(object):
    @pytest.fixture
    def config(self):
        mock = create_autospec(config.Configuration([]), spec_set=True)
        mock.resolve_service.side_effect = config.InvalidConfigurationException("FakeConfig")
        mock.environment = "prod"
        mock.infrastructure = "diy"

        return mock

    @pytest.fixture
    def teams(self):
        return "IO"

    @pytest.fixture
    def tags(self):
        return "cloud"

    @pytest.fixture
    def queue(self):
        return Queue()

    @pytest.fixture
    def reporter(self):
        return create_autospec(Reporter, instance=True)

    @pytest.fixture
    def factory(self):
        mock = create_autospec(SpecFactory, instance=True)
        mock.return_value = APP_SPEC
        return mock

    @pytest.fixture
    def kafka_consumer(self):
        return create_autospec(kafka.KafkaConsumer, instance=True)

    @pytest.fixture
    def consumer(self, queue, config, reporter, factory, kafka_consumer):
        c = pipeline_consumer.Consumer(queue, config, reporter, None, None, factory)
        c._consumer = kafka_consumer
        return c

    def test_fail_on_missing_config(self, consumer):
        with pytest.raises(config.InvalidConfigurationException) as e:
            consumer._connect_kafka()

        assert e.value.message == "FakeConfig"

    def test_create_spec_from_event(self, consumer, factory):
        consumer._create_spec(EVENT)

        assert factory.called
        assert factory.call_count == 1

    def test_fail_if_no_docker_image(self, consumer):
        event = deepcopy(EVENT)
        del event[u"artifacts_by_type"][u"docker"]

        with pytest.raises(pipeline_consumer.NoDockerArtifactException):
            consumer._create_spec(event)

    def test_fail_if_no_fiaas_config(self, consumer):
        event = deepcopy(EVENT)
        del event[u"artifacts_by_type"][u"fiaas"]

        with pytest.raises(pipeline_consumer.NoFiaasArtifactException):
            consumer._create_spec(event)

    def test_deserialize_kafka_message(self, consumer):
        event = consumer._deserialize(MESSAGE)

        assert event == EVENT

    def test_consume_message_in_correct_cluster(self, kafka_consumer, queue, consumer):
        kafka_consumer.__iter__.return_value = [MESSAGE]

        consumer()

        app_spec = queue.get_nowait()
        assert app_spec is APP_SPEC

    def test_skip_message_if_wrong_cluster(self, monkeypatch, kafka_consumer, consumer, queue):
        kafka_consumer.__iter__.return_value = [MESSAGE]
        monkeypatch.setattr(consumer, "_environment", "dev")

        consumer()

        with pytest.raises(Empty):
            queue.get_nowait()

    def test_registers_callback(self, kafka_consumer, consumer, reporter, teams, tags):
        kafka_consumer.__iter__.return_value = [MESSAGE]

        consumer()

        reporter.register.assert_called_with(APP_SPEC.image, EVENT[u"callback_url"])

    def test_should_not_deploy_apps_to_gke_prod_not_in_whitelist(self, monkeypatch, kafka_consumer, factory, queue, consumer):
        kafka_consumer.__iter__.return_value = [MESSAGE]
        monkeypatch.setattr(consumer._config, "infrastructure", "gke")
        factory.return_value = APP_SPEC
        consumer()
        with pytest.raises(Empty):
            queue.get_nowait()

    def test_should_deploy_apps_to_gke_prod_in_whitelist(self, monkeypatch, kafka_consumer, factory, queue, consumer):
        kafka_consumer.__iter__.return_value = [MESSAGE]
        monkeypatch.setattr(consumer._config, "infrastructure", "gke")
        factory.return_value = APP_SPEC_TRAVEL
        consumer()
        app_spec = queue.get_nowait()
        assert app_spec is APP_SPEC_TRAVEL


def _make_env_message(template, env):
    message = deepcopy(template)
    message[u"environment"] = env
    return message
