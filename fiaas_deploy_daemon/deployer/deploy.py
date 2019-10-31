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

import logging

from .kubernetes.ready_check import ReadyCheck
from ..base_thread import DaemonThread
from ..log_extras import set_extras

LOG = logging.getLogger(__name__)


class Deployer(DaemonThread):
    """Take incoming AppSpecs and use the framework-adapter to deploy the app

    Mainly focused on bookkeeping, and leaving the hard work to the framework-adapter.
    """

    def __init__(self, deploy_queue, bookkeeper, adapter, scheduler, lifecycle):
        super(Deployer, self).__init__()
        self._queue = _make_gen(deploy_queue.get)
        self._bookkeeper = bookkeeper
        self._adapter = adapter
        self._scheduler = scheduler
        self._lifecycle = lifecycle

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
        repository = _repository(app_spec)
        try:
            self._lifecycle.start(app_name=app_spec.name,
                                  namespace=app_spec.namespace,
                                  deployment_id=app_spec.deployment_id,
                                  repository=repository,
                                  labels=app_spec.labels.status,
                                  annotations=app_spec.annotations.status)
            with self._bookkeeper.time(app_spec):
                self._adapter.deploy(app_spec)
            if app_spec.name != "fiaas-deploy-daemon":
                self._scheduler.add(ReadyCheck(app_spec, self._bookkeeper, self._lifecycle))
            else:
                self._lifecycle.success(app_name=app_spec.name,
                                        namespace=app_spec.namespace,
                                        deployment_id=app_spec.deployment_id,
                                        repository=repository,
                                        labels=app_spec.labels.status,
                                        annotations=app_spec.annotations.status)
                self._bookkeeper.success(app_spec)
            LOG.info("Completed deployment of %r", app_spec)
        except Exception:
            self._lifecycle.failed(app_name=app_spec.name,
                                   namespace=app_spec.namespace,
                                   deployment_id=app_spec.deployment_id,
                                   repository=repository,
                                   labels=app_spec.labels.status,
                                   annotations=app_spec.annotations.status)
            self._bookkeeper.failed(app_spec)
            LOG.exception("Error while deploying %s: ", app_spec.name)

    def _delete(self, app_spec):
        self._adapter.delete(app_spec)
        LOG.info("Completed removal of %r", app_spec)


def _make_gen(func):
    while True:
        yield func()


def _repository(app_spec):
    try:
        return app_spec.annotations.deployment["fiaas/source-repository"]
    except (TypeError, KeyError, AttributeError):
        pass
