# coding: utf-8
from __future__ import absolute_import

import logging

from k8s.base import WatchEvent
from k8s.client import NotFound
from k8s.models.common import ObjectMeta
from k8s.models.third_party_resource import ThirdPartyResource, APIVersion
from .types import PaasbetaApplication
from ..base_thread import DaemonThread
from ..deployer import DeployerEvent

LOG = logging.getLogger(__name__)


class Watcher(DaemonThread):
    def __init__(self, spec_factory, deploy_queue):
        super(Watcher, self).__init__()
        self._spec_factory = spec_factory
        self._deploy_queue = deploy_queue

    def __call__(self):
        while True:
            self._watch()

    def _watch(self):
        try:
            for event in PaasbetaApplication.watch_list():
                self._handle_watch_event(event)
        except NotFound:
            self._create_third_party_resource()
        except Exception:
            LOG.exception("Error while watching for changes on PaasbetaApplications")

    def _create_third_party_resource(self):
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
        except (AttributeError, KeyError, TypeError):
            raise ValueError("The Application {} is missing the 'fiaas/deployment_id' label".format(
                application.spec.application))
        app_spec = self._spec_factory(
            name=application.spec.application, image=application.spec.image,
            app_config=application.spec.config.as_dict(), teams=[], tags=[],
            deployment_id=deployment_id, namespace=application.metadata.namespace
        )
        self._deploy_queue.put(DeployerEvent("UPDATE", app_spec))
        LOG.debug("Queued deployment for %s", application.spec.application)

    def _delete(self, application):
        app_spec = self._spec_factory(
            name=application.spec.application, image=application.spec.image,
            app_config=application.spec.config.as_dict(), teams=[], tags=[],
            deployment_id=None, namespace=application.metadata.namespace
        )
        self._deploy_queue.put(DeployerEvent("DELETE", app_spec))
        LOG.debug("Queued delete for %s", application.spec.application)
