# coding: utf-8
from __future__ import absolute_import

import logging

from k8s.base import WatchEvent
from k8s.client import NotFound
from k8s.models.common import ObjectMeta
from k8s.models.custom_resource_definition import CustomResourceDefinition, CustomResourceDefinitionSpec, \
    CustomResourceDefinitionNames
from k8s.watcher import Watcher

from .types import FiaasApplication
from ..base_thread import DaemonThread
from ..deployer import DeployerEvent

LOG = logging.getLogger(__name__)


class CrdWatcher(DaemonThread):
    def __init__(self, spec_factory, deploy_queue):
        super(CrdWatcher, self).__init__()
        self._spec_factory = spec_factory
        self._deploy_queue = deploy_queue
        self._watcher = Watcher(FiaasApplication)

    def __call__(self):
        while True:
            self._watch()

    def _watch(self):
        try:
            for event in self._watcher.watch():
                self._handle_watch_event(event)
        except NotFound:
            self._create_custom_resource_definitions()
        except Exception:
            LOG.exception("Error while watching for changes on FiaasApplications")

    def _create_custom_resource_definitions(self):
        self._create("Application", "applications", ("app", "fa"), "fiaas.schibsted.io")
        self._create("Status", "statuses", ("status", "fs"), "fiaas.schibsted.io")

    def _create(self, kind, plural, short_names, group):
        name = "%s.%s" % (plural, group)
        metadata = ObjectMeta(name=name)
        names = CustomResourceDefinitionNames(kind=kind, plural=plural, shortNames=short_names)
        spec = CustomResourceDefinitionSpec(group=group, names=names, version="v1")
        definition = CustomResourceDefinition.get_or_create(metadata=metadata, spec=spec)
        definition.save()
        LOG.info("Created CustomResourceDefinition with name %s", name)

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
        except (AttributeError, KeyError, TypeError):
            raise ValueError("The Application {} is missing the 'fiaas/deployment_id' label".format(
                application.spec.application))
        app_spec = self._spec_factory(
            name=application.spec.application,
            image=application.spec.image,
            app_config=application.spec.config,
            teams=[],
            tags=[],
            deployment_id=deployment_id,
            namespace=application.metadata.namespace
        )
        self._deploy_queue.put(DeployerEvent("UPDATE", app_spec))
        LOG.debug("Queued deployment for %s", application.spec.application)

    def _delete(self, application):
        app_spec = self._spec_factory(
            name=application.spec.application,
            image=application.spec.image,
            app_config=application.spec.config,
            teams=[],
            tags=[],
            deployment_id=None,
            namespace=application.metadata.namespace
        )
        self._deploy_queue.put(DeployerEvent("DELETE", app_spec))
        LOG.debug("Queued delete for %s", application.spec.application)
