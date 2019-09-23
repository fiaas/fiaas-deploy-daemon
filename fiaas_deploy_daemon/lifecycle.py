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


from blinker import signal

DEPLOY_FAILED = "deploy_failed"
DEPLOY_STARTED = "deploy_started"
DEPLOY_SUCCESS = "deploy_success"
DEPLOY_INITIATED = "deploy_initiated"


class Lifecycle(object):
    deploy_signal = signal(DEPLOY_STARTED, "Signals start of deployment")
    error_signal = signal(DEPLOY_FAILED, "Signals a failed deployment")
    success_signal = signal(DEPLOY_SUCCESS, "Signals a successful deployment")
    initiate_signal = signal(DEPLOY_INITIATED, "Signals an initiated deployment")

    def start(self, app_name, namespace, deployment_id, repository=None):
        self.deploy_signal.send(app_name=app_name, namespace=namespace, deployment_id=deployment_id,
                                repository=repository)

    def failed(self, app_name, namespace, deployment_id, repository=None):
        self.error_signal.send(app_name=app_name, namespace=namespace, deployment_id=deployment_id,
                               repository=repository)

    def success(self, app_name, namespace, deployment_id, repository=None):
        self.success_signal.send(app_name=app_name, namespace=namespace, deployment_id=deployment_id,
                                 repository=repository)

    def initiate(self, app_name, namespace, deployment_id, repository=None):
        self.initiate_signal.send(app_name=app_name, namespace=namespace, deployment_id=deployment_id,
                                  repository=repository)
