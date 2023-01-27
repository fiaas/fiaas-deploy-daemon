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


import collections
import logging

import backoff
import requests
from blinker import signal
from prometheus_client import Counter, Histogram

from fiaas_deploy_daemon.base_thread import DaemonThread
from fiaas_deploy_daemon.lifecycle import DEPLOY_STATUS_CHANGED, STATUS_STARTED, STATUS_SUCCESS, STATUS_FAILED
from fiaas_deploy_daemon.tools import IterableQueue

LOG = logging.getLogger(__name__)

UsageEvent = collections.namedtuple("UsageEvent", ("status", "app_name", "namespace", "deployment_id", "repository"))

reporting_histogram = Histogram("fiaas_usage_reporting_latency", "Request latency in seconds")
reporting_success_counter = Counter("fiaas_usage_reporting_success", "Number of successfully reported usage events")
reporting_retry_counter = Counter("fiaas_usage_reporting_retry", "Number of retries when reporting usage events")
reporting_failure_counter = Counter("fiaas_usage_reporting_failure", "Number of failures when reporting usage events")


def _success_handler(details):
    reporting_success_counter.inc()


def _retry_handler(details):
    reporting_retry_counter.inc()


def _failure_handler(details):
    reporting_failure_counter.inc()


class UsageReporter(DaemonThread):
    def __init__(self, config, usage_transformer, session, usage_auth):
        super(UsageReporter, self).__init__()
        self._session = session
        self._transformer = usage_transformer
        self._event_queue = IterableQueue()
        self._usage_reporting_endpoint = config.usage_reporting_endpoint
        self._usage_auth = usage_auth
        if self._usage_reporting_endpoint and self._usage_auth:
            LOG.info("Usage reporting enabled, sending events to %s", self._usage_reporting_endpoint)
            signal(DEPLOY_STATUS_CHANGED).connect(self._handle_signal)
        else:
            LOG.debug(
                "Usage reporting disabled: Endpoint: %r, UsageAuth: %r",
                self._usage_reporting_endpoint,
                self._usage_auth,
            )

    def _handle_signal(self, sender, status, subject):
        if status in [STATUS_STARTED, STATUS_SUCCESS, STATUS_FAILED]:
            status = status.upper()
            self._event_queue.put(
                UsageEvent(status, subject.app_name, subject.namespace, subject.deployment_id, subject.repository)
            )

    def __call__(self):
        for event in self._event_queue:
            self._handle_event(event)

    def _handle_event(self, event):
        data = self._transformer(event.status, event.app_name, event.namespace, event.deployment_id, event.repository)
        try:
            self._send_data(data)
        except requests.exceptions.RequestException:
            LOG.error("Unable to send usage reporting event", exc_info=True)

    @backoff.on_exception(
        backoff.expo,
        requests.exceptions.RequestException,
        max_tries=5,
        on_success=_success_handler,
        on_backoff=_retry_handler,
        on_giveup=_failure_handler,
    )
    @reporting_histogram.time()
    def _send_data(self, data):
        resp = self._session.post(self._usage_reporting_endpoint, json=data, auth=self._usage_auth)
        resp.raise_for_status()
