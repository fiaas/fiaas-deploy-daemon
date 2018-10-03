#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import unicode_literals, absolute_import

import collections
import logging

from blinker import signal

from fiaas_deploy_daemon.base_thread import DaemonThread
from fiaas_deploy_daemon.deployer.bookkeeper import DEPLOY_FAILED, DEPLOY_STARTED, DEPLOY_SUCCESS
from fiaas_deploy_daemon.tools import IterableQueue

LOG = logging.getLogger(__name__)

UsageEvent = collections.namedtuple("UsageEvent", ("status", "app_spec"))


class UsageReporter(DaemonThread):
    def __init__(self, config, usage_transformer, session, usage_auth):
        super(UsageReporter, self).__init__()
        self._session = session
        self._transformer = usage_transformer
        self._event_queue = IterableQueue()
        self._tracking_endpoint = config.tracking_endpoint
        self._usage_auth = usage_auth
        if self._tracking_endpoint and self._usage_auth:
            LOG.info("Usage tracking enabled, sending events to %s", self._tracking_endpoint)
            signal(DEPLOY_STARTED).connect(self._handle_started)
            signal(DEPLOY_SUCCESS).connect(self._handle_success)
            signal(DEPLOY_FAILED).connect(self._handle_failed)
        else:
            LOG.debug("Usage tracking disabled: Endpoint: %r, UsageAuth: %r", self._tracking_endpoint, self._usage_auth)

    def _handle_signal(self, status, app_spec):
        self._event_queue.put(UsageEvent(status, app_spec))

    def _handle_started(self, sender, app_spec):
        self._handle_signal("STARTED", app_spec)

    def _handle_failed(self, sender, app_spec):
        self._handle_signal("FAILED", app_spec)

    def _handle_success(self, sender, app_spec):
        self._handle_signal("SUCCESS", app_spec)

    def __call__(self):
        for event in self._event_queue:
            self._handle_event(event)

    def _handle_event(self, event):
        data = self._transformer(event.status, event.app_spec)
        self._session.post(self._tracking_endpoint, json=data, auth=self._usage_auth)
