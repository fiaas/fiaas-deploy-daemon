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

from collections import namedtuple
from blinker import signal

DEPLOY_STATUS_CHANGED = "deploy_status_changed"

STATUS_FAILED = "failed"
STATUS_STARTED = "started"
STATUS_SUCCESS = "success"
STATUS_INITIATED = "initiated"


Subject = namedtuple(
    "Subject", ("uid", "app_name", "namespace", "deployment_id", "repository", "labels", "annotations")
)


class Lifecycle(object):
    state_change_signal = signal(DEPLOY_STATUS_CHANGED, "Signals a change in the state of a deploy")

    def change(self, status, subject):
        self.state_change_signal.send(status=status, subject=subject)

    def initiate(
        self, uid, app_name, namespace, deployment_id, repository=None, labels=None, annotations=None
    ) -> Subject:
        subject = Subject(uid, app_name, namespace, deployment_id, repository, labels, annotations)
        self.state_change_signal.send(status=STATUS_INITIATED, subject=subject)
        return subject

    def start(self, subject: Subject):
        self.change(STATUS_STARTED, subject)

    def success(self, subject: Subject):
        self.change(STATUS_SUCCESS, subject)

    def failed(self, subject: Subject):
        self.change(STATUS_FAILED, subject)
