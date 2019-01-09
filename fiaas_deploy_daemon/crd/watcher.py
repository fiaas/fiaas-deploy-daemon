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
from ..log_extras import set_extras

from ..specs.factory import InvalidConfiguration
from yaml import YAMLError

LOG = logging.getLogger(__name__)


class CrdWatcher(DaemonThread):
    def __init__(self, spec_factory, deploy_queue, config, lifecycle):
        super(CrdWatcher, self).__init__()
        self._spec_factory = spec_factory
        self._deploy_queue = deploy_queue
        self._watcher = Watcher(FiaasApplication)
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
            self.create_custom_resource_definitions()
        except Exception:
            LOG.exception("Error while watching for changes on FiaasApplications")

    @classmethod
    def create_custom_resource_definitions(cls):
        cls._create("Application", "applications", ("app", "fa"), "fiaas.schibsted.io")
        cls._create("ApplicationStatus", "application-statuses", ("status", "appstatus", "fs"), "fiaas.schibsted.io")

    @staticmethod
    def _create(kind, plural, short_names, group):
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
                name=application.spec.application,
                image=application.spec.image,
                app_config=application.spec.config,
                teams=[],
                tags=[],
                deployment_id=deployment_id,
                namespace=application.metadata.namespace
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
            namespace=application.metadata.namespace
        )
        set_extras(app_spec)
        self._deploy_queue.put(DeployerEvent("DELETE", app_spec))
        LOG.debug("Queued delete for %s", application.spec.application)


def _repository(application):
    try:
        return application.metadata.annotations["deployment"]["fiaas/source-repository"]
    except (TypeError, KeyError, AttributeError):
        pass
