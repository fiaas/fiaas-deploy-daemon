#!/usr/bin/env python
# -*- coding: utf-8

import time
from Queue import PriorityQueue

from monotonic import monotonic as time_monotonic

from ..base_thread import DaemonThread


class Scheduler(DaemonThread):
    def __init__(self, time_func=time_monotonic, delay_func=time.sleep):
        super(Scheduler, self).__init__()
        self._tasks = PriorityQueue()
        self._time_func = time_func
        self._delay_func = delay_func

    def __call__(self, *args, **kwargs):
        while True:
            execute_at, task = self._tasks.get()
            if self._time_func() >= execute_at:
                if task():
                    self.add(task, 10)
            else:
                self.add(task)
            self._delay_func(1)

    def add(self, task, delay=1):
        execute_at = self._time_func() + delay
        self._tasks.put((execute_at, task))
