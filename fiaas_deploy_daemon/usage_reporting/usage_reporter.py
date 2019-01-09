#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import unicode_literals, absolute_import

import collections
import logging

import backoff
import requests
from blinker import signal
from prometheus_client import Counter, Histogram

from fiaas_deploy_daemon.base_thread import DaemonThread
from fiaas_deploy_daemon.lifecycle import DEPLOY_FAILED, DEPLOY_STARTED, DEPLOY_SUCCESS
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
    LOG.warning()


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
            signal(DEPLOY_STARTED).connect(self._handle_started)
            signal(DEPLOY_SUCCESS).connect(self._handle_success)
            signal(DEPLOY_FAILED).connect(self._handle_failed)
        else:
            LOG.debug("Usage reporting disabled: Endpoint: %r, UsageAuth: %r",
                      self._usage_reporting_endpoint, self._usage_auth)

    def _handle_signal(self, status, app_name, namespace, deployment_id, repository):
        self._event_queue.put(UsageEvent(status, app_name, namespace, deployment_id, repository))

    def _handle_started(self, sender, app_name, namespace, deployment_id, repository):
        self._handle_signal("STARTED", app_name, namespace, deployment_id, repository)

    def _handle_failed(self, sender, app_name, namespace, deployment_id, repository):
        self._handle_signal("FAILED", app_name, namespace, deployment_id, repository)

    def _handle_success(self, sender, app_name, namespace, deployment_id, repository):
        self._handle_signal("SUCCESS", app_name, namespace, deployment_id, repository)

    def __call__(self):
        for event in self._event_queue:
            self._handle_event(event)

    def _handle_event(self, event):
        data = self._transformer(event.status, event.app_name, event.namespace, event.deployment_id, event.repository)
        try:
            self._send_data(data)
        except requests.exceptions.RequestException:
            pass  # The backoff handler has already logged this error

    @backoff.on_exception(backoff.expo,
                          requests.exceptions.RequestException,
                          max_tries=5,
                          on_success=_success_handler,
                          on_backoff=_retry_handler,
                          on_giveup=_failure_handler)
    @reporting_histogram.time()
    def _send_data(self, data):
        resp = self._session.post(self._usage_reporting_endpoint, json=data, auth=self._usage_auth)
        resp.raise_for_status()
