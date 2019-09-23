
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

# coding: utf-8
from __future__ import absolute_import

import logging

from k8s.base import WatchEvent
from k8s.client import NotFound
from k8s.models.common import ObjectMeta
from k8s.models.third_party_resource import ThirdPartyResource, APIVersion
from k8s.watcher import Watcher

from fiaas_deploy_daemon.log_extras import set_extras
from .types import PaasbetaApplication
from ..base_thread import DaemonThread
from ..deployer import DeployerEvent
from ..specs.factory import InvalidConfiguration
from yaml import YAMLError

LOG = logging.getLogger(__name__)


class TprWatcher(DaemonThread):
    def __init__(self, spec_factory, deploy_queue, config, lifecycle):
        super(TprWatcher, self).__init__()
        self._spec_factory = spec_factory
        self._deploy_queue = deploy_queue
        self._watcher = Watcher(PaasbetaApplication)
        self._lifecycle = lifecycle
        self.namespace = config.namespace
        self.enable_deprecated_multi_namespace_support = config.enable_deprecated_multi_namespace_support

    def __call__(self):
        while True:
            if self.enable_deprecated_multi_namespace_support:
                self._watch(namespace=None)
            else:
                self._watch(namespace=self.namespace)

    def _watch(self, namespace):
        try:
            for event in self._watcher.watch(namespace=namespace):
                self._handle_watch_event(event)
        except NotFound:
            self.create_third_party_resource()
        except Exception:
            LOG.exception("Error while watching for changes on PaasbetaApplications")

    @staticmethod
    def create_third_party_resource():
        metadata = ObjectMeta(name="paasbeta-application.schibsted.io")
        paasbeta_application_resource = ThirdPartyResource.get_or_create(
            metadata=metadata, description='A paas application definition', versions=[APIVersion(name='v1beta')])
        paasbeta_application_resource.save()
        LOG.debug("Created ThirdPartyResource with name PaasbetaApplication")
        metadata = ObjectMeta(name="paasbeta-status.schibsted.io")
        paasbeta_status_resource = ThirdPartyResource.get_or_create(
            metadata=metadata, description='A paas application status', versions=[APIVersion(name='v1beta')])
        paasbeta_status_resource.save()
        LOG.debug("Created ThirdPartyResource with name PaasbetaStatus")

    def _handle_watch_event(self, event):
        if event.type in (WatchEvent.ADDED, WatchEvent.MODIFIED):
            self._deploy(event.object)
        elif event.type == WatchEvent.DELETED:
            self._delete(event.object)
        else:
            raise ValueError("Unknown WatchEvent type {}".format(event.type))

    def _deploy(self, application):
        LOG.debug("Deploying %s", application.spec.application)
        try:
            deployment_id = application.metadata.labels["fiaas/deployment_id"]
            set_extras(app_name=application.spec.application,
                       namespace=application.metadata.namespace,
                       deployment_id=deployment_id)
        except (AttributeError, KeyError, TypeError):
            raise ValueError("The Application {} is missing the 'fiaas/deployment_id' label".format(
                application.spec.application))
        try:
            repository = _repository(application)
            self._lifecycle.initiate(app_name=application.spec.application, namespace=application.metadata.namespace,
                                     deployment_id=deployment_id, repository=repository)
            app_spec = self._spec_factory(
                name=application.spec.application, image=application.spec.image,
                app_config=application.spec.config, teams=[], tags=[],
                deployment_id=deployment_id, namespace=application.metadata.namespace
            )
            set_extras(app_spec)
            self._deploy_queue.put(DeployerEvent("UPDATE", app_spec))
            LOG.debug("Queued deployment for %s", application.spec.application)
        except (InvalidConfiguration, YAMLError):
            LOG.exception("Failed to create app spec from fiaas config file")
            self._lifecycle.failed(app_name=application.spec.application, namespace=application.metadata.namespace,
                                   deployment_id=deployment_id, repository=repository)

    def _delete(self, application):
        app_spec = self._spec_factory(
            name=application.spec.application,
            image=application.spec.image,
            app_config=application.spec.config,
            teams=[],
            tags=[],
            deployment_id="deletion",
            namespace=application.metadata.namespace,
        )
        set_extras(app_spec)
        self._deploy_queue.put(DeployerEvent("DELETE", app_spec))
        LOG.debug("Queued delete for %s", application.spec.application)


def _repository(application):
    try:
        return application.metadata.annotations["deployment"]["fiaas/source-repository"]
    except (TypeError, KeyError, AttributeError):
        pass
