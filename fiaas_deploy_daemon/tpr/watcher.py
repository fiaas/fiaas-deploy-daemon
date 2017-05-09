# coding: utf-8
from __future__ import absolute_import

from ..base_thread import DaemonThread


class Watcher(DaemonThread):
    def __init__(self, config, deploy_queue):
        super(Watcher, self).__init__()
        self._deploy_queue = deploy_queue

    def is_alive(self):
        return True

    def __call__(self):
        pass
