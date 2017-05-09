# coding: utf-8
from __future__ import absolute_import

import logging
import time

from ..base_thread import DaemonThread
from .paasbetaapplication import PaasbetaApplication

LOG = logging.getLogger(__name__)


class Watcher(DaemonThread):
    def __init__(self, spec_factory, deploy_queue, poll_interval_seconds=1):
        super(Watcher, self).__init__()
        self._spec_factory = spec_factory
        self._deploy_queue = deploy_queue
        self._poll_interval_seconds = poll_interval_seconds
        # TODO: we rely on k8s client being configured in adapter.py. setup should be moved to fdd/__init__.py

    def is_alive(self):
        return True

    def __call__(self):
        while True:
            try:
                time.sleep(self._poll_interval_seconds)

                applications = PaasbetaApplication.list()
                for application in applications:
                    self._deploy(application)
            except:
                LOG.exception("Error while deploying or listing PaasbetaApplication")

    def _deploy(self, application):
        LOG.debug("Deploying %s", application.spec.application)
        app_spec = self._spec_factory(
            name=application.spec.application, image=application.spec.image,
            app_config=application.spec.config.as_dict(), teams=[], tags=[]
        )
        self._deploy_queue.put(app_spec)
        LOG.debug("Queued deployment for %s", application.spec.application)
