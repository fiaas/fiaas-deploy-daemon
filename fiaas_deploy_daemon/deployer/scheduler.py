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
import time
from queue import PriorityQueue
from time import monotonic as time_monotonic
from typing import Callable

from k8s.client import K8sClientException
from requests.exceptions import RetryError

from ..base_thread import DaemonThread

LOG = logging.getLogger(__name__)


class Scheduler(DaemonThread):
    def __init__(self, time_func=time_monotonic, delay_func=time.sleep):
        super(Scheduler, self).__init__()
        self._tasks = PriorityQueue()
        self._time_func: Callable[[], float] = time_func
        self._delay_func: Callable[[float], None] = delay_func

    def __call__(self, *args, run_forever=True, **kwargs):
        while True:
            execute_at, task = self._tasks.get()
            if self._time_func() >= execute_at:
                try:
                    if task():
                        self.add(task, 10)
                except (K8sClientException, RetryError):
                    # K8sClientException: any unhandled server or client error (non-200 responses).
                    # RetryError: request which received server error (e.g. 409 or 5xx response) was retried, and
                    # exponential retries were exhausted.
                    LOG.exception("Error while processing task")
            else:
                self.add(task)
            self._delay_func(1)
            # the run_forever parameter is only to enable testing
            if not run_forever:
                LOG.warning("breaking task processing loop because run_forever=%s", run_forever)
                break

    def add(self, task: Callable[[], bool], delay=1):
        execute_at = self._time_func() + delay
        self._tasks.put((execute_at, task))
