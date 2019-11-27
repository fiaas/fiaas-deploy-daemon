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

from __future__ import absolute_import

import logging
import posixpath

from blinker import signal

from fiaas_deploy_daemon.log_extras import get_final_logs
from ..lifecycle import DEPLOY_STATUS_CHANGED, STATUS_STARTED, STATUS_SUCCESS, STATUS_FAILED


class Reporter(object):
    """Report results of deployments to pipeline"""
    def __init__(self, config, session):
        self._environment = config.environment
        self._infrastructure = config.infrastructure
        self._session = session
        self._callback_urls = {}
        self._logger = logging.getLogger(__name__)
        signal(DEPLOY_STATUS_CHANGED).connect(self._handle_status_changed)

    def register(self, app_spec, url):
        self._callback_urls[(app_spec.name, app_spec.deployment_id)] = url

    def _handle_status_changed(self, sender, status, subject):
        if status == STATUS_STARTED:
            self._handle_signal("deploy_started", subject.app_name, subject.namespace, subject.deployment_id)
        elif status == STATUS_SUCCESS:
            self._handle_signal(u"deploy_end", subject.app_name, subject.namespace, subject.deployment_id)
        elif status == STATUS_FAILED:
            self._handle_signal(u"deploy_end", subject.app_name, subject.namespace, subject.deployment_id, status=u"failure")

    def _handle_signal(self, event_name, app_name, namespace, deployment_id, status=u"success"):
        base_url = self._callback_urls.get((app_name, deployment_id))
        if not base_url:
            self._logger.info(
                "No base URL for {} (deployment_id={}) found, not posting to pipeline".format(app_name, deployment_id))
            return
        task_name = u"fiaas_{}-{}_{}".format(self._environment, self._infrastructure, event_name)
        url = posixpath.join(base_url, task_name, status)
        r = self._session.post(url, json={u"description": u"From fiaas-deploy-daemon"})
        self._logger.info("Posted {} for app {} (deployment_id={}) to pipeline, return code={}".format(
            status, app_name, deployment_id, r.status_code))
        self._empty_status_logs(app_name, namespace, deployment_id)

    @staticmethod
    def _empty_status_logs(app_name, namespace, deployment_id):
        """Clear the status logs from the collector

        Pipeline doesn't have a good place to dump the logs, so we just make sure to empty out the log-collector every
        time we handle a signal. Once this code is taken out of fiaas-deploy-daemon, this is no longer a problem.
        """
        get_final_logs(app_name, namespace, deployment_id)
