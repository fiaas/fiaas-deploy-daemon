
import json
from Queue import Queue, Empty
from collections import namedtuple
from copy import deepcopy

import kafka
import pytest
from mock import create_autospec, patch
from requests import HTTPError
from yaml import YAMLError

from fiaas_deploy_daemon import config
from fiaas_deploy_daemon.lifecycle import Lifecycle
from fiaas_deploy_daemon.pipeline import consumer as pipeline_consumer
from fiaas_deploy_daemon.pipeline.reporter import Reporter
from fiaas_deploy_daemon.specs.app_config_downloader import AppConfigDownloader
from fiaas_deploy_daemon.specs.factory import InvalidConfiguration

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
    u'teams': [u'IO'],
    u'tags': [u'cloud'],
    u'timestamp': u'2016-01-05T15:20:26+01:00',
    u'user': u'fikameva'
}
MESSAGE = DummyMessage(json.dumps(EVENT))


class TestConsumer(object):
    @pytest.fixture
    def config(self):
        mock = create_autospec(config.Configuration([]), spec_set=True)
        mock.resolve_service.side_effect = config.InvalidConfigurationException("FakeConfig")
        mock.environment = "prod"
        mock.infrastructure = "diy"
        return mock

    @pytest.fixture
    def queue(self):
        return Queue()

    @pytest.fixture
    def reporter(self):
        return create_autospec(Reporter, instance=True)

    @pytest.fixture
    def factory(self, app_spec):
        with patch('fiaas_deploy_daemon.specs.factory.SpecFactory') as mock:
            mock.return_value = app_spec
            yield mock

    @pytest.fixture
    def app_config(self):
        return {'version': 2}  # minimal v2 yaml

    @pytest.fixture
    def app_config_downloader(self, app_config):
        mock = create_autospec(AppConfigDownloader, instance=True)
        mock.get.return_value = app_config
        return mock

    @pytest.fixture
    def kafka_consumer(self):
        return create_autospec(kafka.KafkaConsumer, instance=True)

    @pytest.fixture
    def lifecycle(self):
        return create_autospec(Lifecycle, instance=True)

    @pytest.fixture
    def consumer(self, queue, config, reporter, factory, kafka_consumer, app_config_downloader, lifecycle):
        c = pipeline_consumer.Consumer(queue, config, reporter, factory, app_config_downloader, lifecycle)
        c._consumer = kafka_consumer
        return c

    def test_fail_on_missing_config(self, consumer):
        with pytest.raises(config.InvalidConfigurationException) as e:
            consumer._connect_kafka()

        assert e.value.message == "FakeConfig"

    def test_create_spec_from_event(self, consumer, factory, app_config_downloader, app_config):
        consumer._create_spec(EVENT)

        assert app_config_downloader.get.called
        assert app_config_downloader.get.call_count == 1

        image = EVENT[u"artifacts_by_type"][u"docker"]
        factory.assert_called_once_with(EVENT[u"project_name"], image, app_config, EVENT[u"teams"], EVENT[u"tags"],
                                        image.split(":")[-1], pipeline_consumer.DEFAULT_NAMESPACE)

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

    def test_consume_message_in_correct_cluster(self, kafka_consumer, queue, consumer, app_spec):
        kafka_consumer.__iter__.return_value = [MESSAGE]

        consumer()

        result = queue.get_nowait()
        assert app_spec is result.app_spec
        assert result.action == "UPDATE"

    def test_skip_message_if_wrong_cluster(self, monkeypatch, kafka_consumer, consumer, queue):
        kafka_consumer.__iter__.return_value = [MESSAGE]
        monkeypatch.setattr(consumer, "_environment", "dev")

        consumer()

        with pytest.raises(Empty):
            queue.get_nowait()

    def test_registers_callback(self, kafka_consumer, consumer, reporter, app_spec):
        kafka_consumer.__iter__.return_value = [MESSAGE]

        consumer()

        reporter.register.assert_called_with(app_spec, EVENT[u"callback_url"])

    def test_should_not_deploy_apps_not_in_whitelist(self, monkeypatch, kafka_consumer, factory, queue, consumer, app_spec):
        kafka_consumer.__iter__.return_value = [MESSAGE]
        monkeypatch.setattr(consumer._config, "whitelist", ["white_app"])
        factory.return_value = app_spec
        consumer()
        with pytest.raises(Empty):
            queue.get_nowait()

    def test_should_deploy_apps_in_whitelist(self, monkeypatch, kafka_consumer, factory, queue, consumer, app_spec):
        kafka_consumer.__iter__.return_value = [MESSAGE]
        monkeypatch.setattr(consumer._config, "whitelist", ["testapp"])
        factory.return_value = app_spec
        consumer()
        result = queue.get_nowait()
        assert app_spec is result.app_spec
        assert result.action == "UPDATE"

    def test_should_not_deploy_apps_in_blacklist(self, monkeypatch, kafka_consumer, factory, queue, consumer, app_spec):
        kafka_consumer.__iter__.return_value = [MESSAGE]
        monkeypatch.setattr(consumer._config, "blacklist", ["testapp"])
        factory.return_value = app_spec

        consumer()

        with pytest.raises(Empty):
            queue.get_nowait()

    def test_initiates_lifecycle(self, consumer, lifecycle, kafka_consumer):
        kafka_consumer.__iter__.return_value = [MESSAGE]

        consumer()

        lifecycle.initiate.assert_called_once()

    @pytest.mark.parametrize("error", (YAMLError, InvalidConfiguration))
    def test_fail_if_invalid_fiaas_config(self, consumer, kafka_consumer, factory, lifecycle, error):
        factory.side_effect = error()

        kafka_consumer.__iter__.return_value = [MESSAGE]

        consumer()

        lifecycle.failed.assert_called_once()

    def test_fail_on_download_error(self, consumer, kafka_consumer, app_config_downloader, lifecycle):
        app_config_downloader.get.side_effect = HTTPError()
        kafka_consumer.__iter__.return_value = [MESSAGE]

        consumer()

        lifecycle.failed.assert_called_once()


def _make_env_message(template, env):
    message = deepcopy(template)
    message[u"environment"] = env
    return message
