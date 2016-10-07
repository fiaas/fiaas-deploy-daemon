#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import logging

from .kubernetes.ready_check import ReadyCheck
from ..base_thread import DaemonThread

LOG = logging.getLogger(__name__)


class Deployer(DaemonThread):
    """Take incoming AppSpecs and use the framework-adapter to deploy the app

    Mainly focused on bookkeeping, and leaving the hard work to the framework-adapter.
    """

    def __init__(self, deploy_queue, bookkeeper, adapter, scheduler):
        super(Deployer, self).__init__()
        self._queue = _make_gen(deploy_queue.get)
        self._bookkeeper = bookkeeper
        self._adapter = adapter
        self._scheduler = scheduler

    def __call__(self):
        for app_spec in self._queue:
            LOG.info("Received %r for deployment", app_spec)
            try:
                with self._bookkeeper.time(app_spec):
                    self._adapter.deploy(app_spec)
                self._scheduler.add(ReadyCheck(app_spec, self._bookkeeper))
                LOG.info("Completed deployment of %r", app_spec)
            except Exception:
                self._bookkeeper.failed(app_spec)
                LOG.exception("Error while deploying: ")


def _make_gen(func):
    while True:
        yield func()
