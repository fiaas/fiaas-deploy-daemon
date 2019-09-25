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
from __future__ import absolute_import

import json
import logging
import os
import time

from kafka import KafkaConsumer
from monotonic import monotonic as time_monotonic
from prometheus_client import Counter
from requests import HTTPError
from yaml import YAMLError

from fiaas_deploy_daemon.log_extras import set_extras
from ..base_thread import DaemonThread
from ..deployer import DeployerEvent
from ..specs.factory import InvalidConfiguration

ALLOW_WITHOUT_MESSAGES_S = int(os.getenv('ALLOW_WITHOUT_MESSAGES_MIN', 30)) * 60
DEFAULT_NAMESPACE = u"default"


class Consumer(DaemonThread):
    """Listen for pipeline events and generate AppSpecs for the deployer

    Requires the following environment variables:
    - KAFKA_PIPELINE_SERVICE_HOST: Comma separated list of kafka brokers
    - KAFKA_PIPELINE_SERVICE_PORT: Port kafka listens on
    """

    def __init__(self, deploy_queue, config, reporter, spec_factory, app_config_downloader, lifecycle):
        super(Consumer, self).__init__()
        self._logger = logging.getLogger(__name__)
        self._deploy_queue = deploy_queue
        self._consumer = None
        self._config = config
        self._environment = config.environment
        self._reporter = reporter
        self._spec_factory = spec_factory
        self._app_config_downloader = app_config_downloader
        self._lifecycle = lifecycle
        self._last_message_timestamp = int(time_monotonic())

    def __call__(self):
        if self._consumer is None:
            self._connect_kafka()
        message_counter = Counter("pipeline_message_received", "A message from pipeline received")
        deploy_counter = Counter("pipeline_deploy_triggered", "A message caused a deploy to be triggered")
        for message in self._consumer:
            self._handle_message(deploy_counter, message, message_counter)

    def _handle_message(self, deploy_counter, message, message_counter):
        message_counter.inc()
        self._last_message_timestamp = int(time_monotonic())
        event = self._deserialize(message)
        self._logger.debug("Got event: %r", event)
        if event[u"environment"] == self._environment:
            try:
                self._lifecycle.initiate(app_name=event[u"project_name"], namespace=DEFAULT_NAMESPACE,
                                         deployment_id=self._deployment_id(event))
                app_spec = self._create_spec(event)
                set_extras(app_spec)
                self._check_app_acceptable(app_spec)
                self._add_deployment_label(app_spec)
                self._deploy_queue.put(DeployerEvent("UPDATE", app_spec))
                self._reporter.register(app_spec, event[u"callback_url"])
                deploy_counter.inc()
            except (NoDockerArtifactException, NoFiaasArtifactException):
                self._logger.debug("Ignoring event %r with missing artifacts", event)
            except YAMLError:
                self._logger.exception("Failure when parsing FIAAS-config")
                self._lifecycle.failed(app_name=event[u"project_name"], namespace=DEFAULT_NAMESPACE,
                                       deployment_id=self._deployment_id(event))
            except InvalidConfiguration:
                self._logger.exception("Invalid configuration for application %s", event.get("project_name"))
                self._lifecycle.failed(app_name=event[u"project_name"], namespace=DEFAULT_NAMESPACE,
                                       deployment_id=self._deployment_id(event))
            except HTTPError:
                self._logger.exception("Failure when downloading FIAAS-config")
                self._lifecycle.failed(app_name=event[u"project_name"], namespace=DEFAULT_NAMESPACE,
                                       deployment_id=self._deployment_id(event))
            except (NotWhiteListedApplicationException, BlackListedApplicationException) as e:
                self._logger.warn("App not deployed. %s", str(e))

    def _check_app_acceptable(self, app_spec):
        if self._config.whitelist and app_spec.name not in self._config.whitelist:
            raise NotWhiteListedApplicationException(
                "{} is not a in whitelist for this cluster".format(app_spec.name))
        if self._config.blacklist and app_spec.name in self._config.blacklist:
            raise BlackListedApplicationException(
                "{} is banned from this cluster".format(app_spec.name))

    def _connect_kafka(self):
        self._consumer = KafkaConsumer(
            "internal.pipeline.deployment",
            bootstrap_servers=self._build_connect_string("kafka_pipeline")
        )

    def _create_spec(self, event):
        artifacts = self._artifacts(event)
        name = event[u"project_name"]
        image = artifacts[u"docker"]
        deployment_id = self._deployment_id(event)
        fiaas_url = artifacts[u"fiaas"]
        teams = event[u"teams"]
        tags = event[u"tags"]

        set_extras(app_name=name, namespace=DEFAULT_NAMESPACE, deployment_id=deployment_id)

        app_config = self._app_config_downloader.get(fiaas_url)

        return self._spec_factory(name, image, app_config, teams, tags, deployment_id,
                                  DEFAULT_NAMESPACE)

    def _artifacts(self, event):
        artifacts = event[u"artifacts_by_type"]
        if u"docker" not in artifacts:
            raise NoDockerArtifactException()
        if u"fiaas" not in artifacts:
            raise NoFiaasArtifactException()
        return artifacts

    def _deployment_id(self, event):
        artifacts = self._artifacts(event)
        image = artifacts[u"docker"]
        deployment_id = image.split(":")[-1][:63].lower()
        return deployment_id

    def _build_connect_string(self, service):
        host, port = self._config.resolve_service(service)
        connect = ",".join("{}:{}".format(host, port) for host in host.split(","))
        return connect

    def is_alive(self):
        return super(Consumer, self).is_alive() and self._is_receiving_messages()

    def _is_receiving_messages(self):
        # TODO: this is a hack to handle the fact that we sometimes seem to loose contact with kafka
        self._logger.debug("No message for %r seconds", int(time_monotonic()) - self._last_message_timestamp)
        return self._last_message_timestamp > int(time_monotonic()) - ALLOW_WITHOUT_MESSAGES_S

    @staticmethod
    def _deserialize(message):
        return json.loads(message.value)

    @staticmethod
    def _add_deployment_label(app_spec):
        app_spec.labels.deployment["fiaas/app_deployed_at"] = str(int(round(time.time())))


class NoDockerArtifactException(Exception):
    pass


class NoFiaasArtifactException(Exception):
    pass


class NotWhiteListedApplicationException(Exception):
    pass


class BlackListedApplicationException(Exception):
    pass
