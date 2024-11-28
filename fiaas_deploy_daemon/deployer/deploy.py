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


import logging
from queue import Queue

from k8s.client import K8sClientException
from requests.exceptions import RetryError

from fiaas_deploy_daemon.config import Configuration
from fiaas_deploy_daemon.deployer.kubernetes.adapter import K8s
from fiaas_deploy_daemon.deployer.kubernetes.ingress import IngressAdapterInterface
from fiaas_deploy_daemon.lifecycle import Lifecycle, Subject

from ..base_thread import DaemonThread
from ..log_extras import set_extras
from ..specs.models import AppSpec
from .bookkeeper import Bookkeeper
from .kubernetes.ready_check import ReadyCheck
from .scheduler import Scheduler

LOG = logging.getLogger(__name__)


class Deployer(DaemonThread):
    """Take incoming AppSpecs and use the framework-adapter to deploy the app

    Mainly focused on bookkeeping, and leaving the hard work to the framework-adapter.
    """

    def __init__(
        self, deploy_queue: Queue, bookkeeper, adapter, scheduler: Scheduler, lifecycle, ingress_adapter, config
    ):
        super(Deployer, self).__init__()
        self._queue = _make_gen(deploy_queue.get)
        self._bookkeeper: Bookkeeper = bookkeeper
        self._adapter: K8s = adapter
        self._scheduler: Scheduler = scheduler
        self._lifecycle: Lifecycle = lifecycle
        self._ingress_adapter: IngressAdapterInterface = ingress_adapter
        self._config: Configuration = config

    def __call__(self):
        for event in self._queue:
            set_extras(event.app_spec)
            LOG.info("Received %r for %s", event.app_spec, event.action)
            if event.action == "UPDATE":
                self._update(event.app_spec, event.lifecycle_subject)
            else:
                raise ValueError("Unknown DeployerEvent action {}".format(event.action))

    def _update(self, app_spec: AppSpec, lifecycle_subject: Subject):
        try:
            self._lifecycle.start(lifecycle_subject)
            with self._bookkeeper.time(app_spec):
                self._adapter.deploy(app_spec)
            if app_spec.name != "fiaas-deploy-daemon":
                self._scheduler.add(
                    ReadyCheck(
                        app_spec,
                        self._bookkeeper,
                        self._lifecycle,
                        lifecycle_subject,
                        self._ingress_adapter,
                        self._config,
                    )
                )
            else:
                self._lifecycle.success(lifecycle_subject)
                self._bookkeeper.success(app_spec)
            LOG.info("Completed deployment of %r", app_spec)
        except Exception:
            LOG.exception("Error while deploying %s: ", app_spec.name)
            try:
                self._lifecycle.failed(lifecycle_subject)
            except (K8sClientException, RetryError):
                # K8sClientException: any unhandled server or client error (non-200 responses).
                # RetryError: request which received server error (e.g. 409 or 5xx response) was retried, and
                # exponential retries were exhausted.
                LOG.exception("Error while saving status for %s: ", app_spec.name)
            self._bookkeeper.failed(app_spec)


def _make_gen(func):
    while True:
        yield func()
