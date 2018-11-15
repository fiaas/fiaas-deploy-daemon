#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import logging

from .kubernetes.ready_check import ReadyCheck
from ..base_thread import DaemonThread
from ..log_extras import set_extras

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
        for event in self._queue:
            set_extras(event.app_spec)
            LOG.info("Received %r for %s", event.app_spec, event.action)
            if event.action == "UPDATE":
                self._update(event.app_spec)
            elif event.action == "DELETE":
                self._delete(event.app_spec)
            else:
                raise ValueError("Unknown DeployerEvent action {}".format(event.action))

    def _update(self, app_spec):
        try:
            with self._bookkeeper.time(app_spec):
                self._adapter.deploy(app_spec)
            if app_spec.name != "fiaas-deploy-daemon":
                self._scheduler.add(ReadyCheck(app_spec, self._bookkeeper))
            else:
                self._bookkeeper.success(app_spec)
            LOG.info("Completed deployment of %r", app_spec)
        except Exception:
            self._bookkeeper.failed(app_spec)
            LOG.exception("Error while deploying %s: ", app_spec.name)

    def _delete(self, app_spec):
        self._adapter.delete(app_spec)
        LOG.info("Completed removal of %r", app_spec)


def _make_gen(func):
    while True:
        yield func()
