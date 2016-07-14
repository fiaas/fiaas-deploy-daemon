#!/usr/bin/env python
# -*- coding: utf-8

from threading import Thread
import logging


class DaemonThread(Thread):
    def __init__(self):
        super(DaemonThread, self).__init__(None, self._logging_target, self._make_name())
        self.daemon = True

    def _logging_target(self):
        log = logging.getLogger()
        try:
            self()
        except:
            log.exception("Error in background thread %s", self.name)

    def _make_name(self):
        return self.__class__.__name__

    def __call__(self, *args, **kwargs):
        raise NotImplementedError("Subclass must implement this method")
