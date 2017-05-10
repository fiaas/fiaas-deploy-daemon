# coding: utf-8
from __future__ import absolute_import

import logging

from ..base_thread import DaemonThread
from .paasbetaapplication import PaasbetaApplication
from k8s.base import WatchEvent

LOG = logging.getLogger(__name__)


class Watcher(DaemonThread):
    def __init__(self, spec_factory, deploy_queue):
        super(Watcher, self).__init__()
        self._spec_factory = spec_factory
        self._deploy_queue = deploy_queue
        # TODO: we rely on k8s client being configured in adapter.py. setup should be moved to fdd/__init__.py

    def is_alive(self):
        return True

    def __call__(self):
        while True:
            try:
                for event in PaasbetaApplication.watch_list():
                    self._handle_watch_event(event)
            except:
                LOG.exception("Error while watching for changes on PaasbetaApplications")

    def _handle_watch_event(self, event):
        if event.type in (WatchEvent.ADDED, WatchEvent.MODIFIED):
            self._deploy(event.object)
        elif event.type == WatchEvent.DELETED:
            pass  # TODO: this should delete the related kubernetes objects
        else:
            raise ValueError("Unknown WatchEvent type {}".format(event.type))

    def _deploy(self, application):
        LOG.debug("Deploying %s", application.spec.application)
        app_spec = self._spec_factory(
            name=application.spec.application, image=application.spec.image,
            app_config=application.spec.config.as_dict(), teams=[], tags=[]
        )
        self._deploy_queue.put(app_spec)
        LOG.debug("Queued deployment for %s", application.spec.application)
