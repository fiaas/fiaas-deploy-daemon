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
