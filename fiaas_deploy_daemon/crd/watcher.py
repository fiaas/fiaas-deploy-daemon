# coding: utf-8

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

from k8s.base import WatchEvent
from k8s.client import NotFound
from k8s.watcher import Watcher
from yaml import YAMLError

from .status import create_name
from .types import FiaasApplication, FiaasApplicationStatus
from ..base_thread import DaemonThread
from ..deployer import DeployerEvent
from ..log_extras import set_extras
from ..specs.factory import InvalidConfiguration

LOG = logging.getLogger(__name__)


class CrdWatcher(DaemonThread):
    def __init__(self, spec_factory, deploy_queue, config, lifecycle, crd_resources_syncer):
        super(CrdWatcher, self).__init__()
        self._spec_factory = spec_factory
        self._deploy_queue = deploy_queue
        self._watcher = Watcher(FiaasApplication)
        self._lifecycle = lifecycle
        self.namespace = config.namespace
        self.enable_deprecated_multi_namespace_support = config.enable_deprecated_multi_namespace_support
        self.crd_resources_syncer = crd_resources_syncer
        self.disable_crd_creation = config.disable_crd_creation

    def __call__(self):
        while True:
            if self.enable_deprecated_multi_namespace_support:
                self._watch(namespace=None)
            else:
                self._watch(namespace=self.namespace)

    def _watch(self, namespace):
        if not self.disable_crd_creation:
            self.crd_resources_syncer.update_crd_resources()
        try:
            for event in self._watcher.watch(namespace=namespace):
                self._handle_watch_event(event)
        except Exception:
            LOG.exception("Error while watching for changes on FiaasApplications")

    def _handle_watch_event(self, event):
        if event.type in (WatchEvent.ADDED, WatchEvent.MODIFIED):
            self._deploy(event.object)
        elif event.type == WatchEvent.DELETED:
            self._delete(event.object)
        else:
            raise ValueError("Unknown WatchEvent type {}".format(event.type))

    # When we receive update event on FiaasApplication
    # don't deploy if it's a status update
    def _skip_status_event(self, application):
        app_name = application.spec.application
        deployment_id = application.metadata.labels["fiaas/deployment_id"]
        app_status = application
        generation = app_status.metadata.generation
        observed_generation = app_status.status.observedGeneration
        if observed_generation == generation:
            LOG.debug("Event created from status update %s for app %s", deployment_id, app_name)
            return True
        return False

    def _deploy(self, application):
        if self._skip_status_event(application):
            return
        app_name = application.spec.application
        LOG.debug("Deploying %s", app_name)
        try:
            deployment_id = application.metadata.labels["fiaas/deployment_id"]
            set_extras(app_name=app_name, namespace=application.metadata.namespace, deployment_id=deployment_id)
        except (AttributeError, KeyError, TypeError):
            raise ValueError("The Application {} is missing the 'fiaas/deployment_id' label".format(app_name))
        if self._already_deployed(app_name, application.metadata.namespace, deployment_id):
            LOG.debug("Have already deployed %s for app %s", deployment_id, app_name)
            return
        repository = _repository(application)
        lifecycle_subject = self._lifecycle.initiate(
            uid=application.metadata.uid,
            app_name=app_name,
            namespace=application.metadata.namespace,
            deployment_id=deployment_id,
            repository=repository,
            labels=application.spec.additional_labels.status,
            annotations=application.spec.additional_annotations.status,
        )
        try:
            app_spec = self._spec_factory(
                uid=application.metadata.uid,
                name=app_name,
                image=application.spec.image,
                app_config=application.spec.config,
                teams=[],
                tags=[],
                deployment_id=deployment_id,
                namespace=application.metadata.namespace,
                additional_labels=application.spec.additional_labels,
                additional_annotations=application.spec.additional_annotations,
            )
            set_extras(app_spec)
            self._deploy_queue.put(DeployerEvent("UPDATE", app_spec, lifecycle_subject))
            LOG.debug("Queued deployment for %s", app_name)
        except (InvalidConfiguration, YAMLError):
            LOG.exception("Failed to create app spec from fiaas config file")
            self._lifecycle.failed(lifecycle_subject)

    def _delete(self, application):
        app_spec = self._spec_factory(
            uid=application.metadata.uid,
            name=application.spec.application,
            image=application.spec.image,
            app_config=application.spec.config,
            teams=[],
            tags=[],
            deployment_id="deletion",
            namespace=application.metadata.namespace,
            additional_labels=application.spec.additional_labels,
            additional_annotations=application.spec.additional_annotations,
        )
        set_extras(app_spec)
        self._deploy_queue.put(DeployerEvent("DELETE", app_spec, lifecycle_subject=None))
        LOG.debug("Queued delete for %s", application.spec.application)

    def _already_deployed(self, app_name, namespace, deployment_id):
        try:
            name = create_name(app_name, deployment_id)
            status = FiaasApplicationStatus.get(name, namespace)
            return status.result == "SUCCESS"
        except NotFound:
            return False


def _repository(application):
    try:
        return application.spec.config["annotations"]["deployment"]["fiaas/source-repository"]
    except (TypeError, KeyError, AttributeError):
        pass
