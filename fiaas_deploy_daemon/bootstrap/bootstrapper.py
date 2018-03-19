# -*- coding: utf-8
from __future__ import absolute_import

from functools import partial
import logging
import threading
import time

from blinker import signal
from monotonic import monotonic as time_monotonic

from ..config import InvalidConfigurationException
from ..crd.types import FiaasApplication
from ..deployer import DeployerEvent
from ..tpr.types import PaasbetaApplication
from ..deployer.bookkeeper import DEPLOY_FAILED, DEPLOY_STARTED, DEPLOY_SUCCESS


LOG = logging.getLogger(__name__)
DEPLOY_SCHEDULED = "deploy_scheduled"


class StatusCollector(object):
    def __init__(self):
        self._statuses = {}
        self._statuses_lock = threading.RLock()

    def store_status(self, status, app_spec):
        with self._statuses_lock:
            self._statuses[self._key(app_spec)] = status
            LOG.info("Received {status} for {name} in namespace {namespace}".format(status=status, name=app_spec.name,
                                                                                    namespace=app_spec.namespace))

    def values(self):
        with self._statuses_lock:
            return self._statuses.values()

    def items(self):
        for key, status in self._statuses.iteritems():
            name, namespace = self._unkey(key)
            yield name, namespace, status

    @staticmethod
    def _key(app_spec):
        return ".".join((app_spec.name, app_spec.namespace))

    @staticmethod
    def _unkey(key):
        name, namespace = key.split(".")
        return name, namespace


class Bootstrapper(object):
    def __init__(self, config, deploy_queue, spec_factory):
        self._deploy_queue = deploy_queue
        self._spec_factory = spec_factory
        self._status_collector = StatusCollector()
        self._store_started = partial(self._store_status, DEPLOY_STARTED)
        self._store_success = partial(self._store_status, DEPLOY_SUCCESS)
        self._store_failed = partial(self._store_status, DEPLOY_FAILED)

        if config.enable_crd_support:
            self._resource_class = FiaasApplication
            from ..crd.status import connect_signals
        elif config.enable_tpr_support:
            self._resource_class = PaasbetaApplication
            from ..tpr.status import connect_signals
        else:
            raise InvalidConfigurationException(
                "Third Party Resource or Custom Resource Definition support must be enabled when bootstrapping")
        connect_signals()
        signal(DEPLOY_STARTED).connect(self._store_started)
        signal(DEPLOY_SUCCESS).connect(self._store_success)
        signal(DEPLOY_FAILED).connect(self._store_failed)

    def run(self):
        for application in self._resource_class.find(name=None, namespace=None, labels={"fiaas/bootstrap": "true"}):
            try:
                self._deploy(application)
            except BaseException:
                LOG.exception("Caught exception when deploying {name} in namespace {namespace}".format(
                    name=application.metadata.name, namespace=application.metadata.namespace))

        return self._wait_for_readiness(wait_time_seconds=2, timeout_seconds=60)

    def _deploy(self, application):
        LOG.debug("Deploying %s", application.spec.application)
        try:
            deployment_id = application.metadata.labels["fiaas/deployment_id"]
        except (AttributeError, KeyError, TypeError):
            raise ValueError("The Application {} is missing the 'fiaas/deployment_id' label".format(
                application.spec.application))
        app_spec = self._spec_factory(
            name=application.spec.application,
            image=application.spec.image,
            app_config=application.spec.config,
            teams=[],
            tags=[],
            deployment_id=deployment_id,
            namespace=application.metadata.namespace
        )
        self._store_status(DEPLOY_SCHEDULED, None, app_spec)
        self._deploy_queue.put(DeployerEvent("UPDATE", app_spec))
        LOG.debug("Queued deployment for %s in namespace %s", application.spec.application,
                  application.metadata.namespace)

    def _store_status(self, status, sender, app_spec):
        self._status_collector.store_status(status, app_spec)

    def _wait_for_readiness(self, wait_time_seconds, timeout_seconds):
        start = time_monotonic()
        while time_monotonic() < (start + timeout_seconds):
            if all(status == DEPLOY_SUCCESS for status in self._status_collector.values()):
                LOG.info("Bootstrapped {} applications".format(len(self._status_collector.values())))
                return True
            else:
                time.sleep(wait_time_seconds)
        else:
            message = "Timed out after waiting {}s  for applications to become ready.\n".format(timeout_seconds)
            message += "Applications which failed to become ready:\n"
            for name, namespace, status in self._status_collector.items():
                message += "{} in namespace {} had final state {}".format(name, namespace, status)
            LOG.error(message)
            return False
