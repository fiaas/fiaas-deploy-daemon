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
        except BaseException:
            log.exception("Error in background thread %s", self.name)

    def _make_name(self):
        return self.__class__.__name__

    def __call__(self, *args, **kwargs):
        raise NotImplementedError("Subclass must implement this method")
