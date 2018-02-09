# -*- coding: utf-8
from __future__ import absolute_import

import logging

from ..config import InvalidConfigurationException
from ..crd.types import FiaasApplication
from ..deployer import DeployerEvent
from ..tpr.types import PaasbetaApplication

LOG = logging.getLogger(__name__)


class Bootstrapper():
    def __init__(self, config, deploy_queue, spec_factory):
        self._deploy_queue = deploy_queue
        self._spec_factory = spec_factory

        if config.enable_crd_support:
            self._resource_class = FiaasApplication
            from ..crd.status import connect_signals
        elif config.enable_tpr_support:
            self._resource_class = PaasbetaApplication
            from ..tpr.status import connect_signals
        else:
            raise InvalidConfigurationException(
                "Third Party Resource or Custom Resource Definition support must be enabled when bootstrapping")
        connect_signals()

    def run(self):
        # 1. list all TPR/CRDs with label fiaas/control-plane=true
        # 2. for each CRD, create app_spec and deploy it
        # 3. wait for readiness checks to complete. This can be done by;
        #    - implementing some sort of wait()-like mechanism in the scheduler, since it knows how many tasks it has
        #      and can block untill it doesn't have any more tasks.
        #    - subscribing to signals and maintaining a set of all the checks expected to succeed and connecting
        #      statuses as they arrive. Essentially the same as above, except the state lives in the bootstrapper.
        # 4. statuses for each deployed app should be printed as they arrive
        # 5. exit 0 if every status was SUCCESS, 1 otherwise
        for application in self.resource_class.list():
            try:
                self._deploy(application)
            except BaseException:
                LOG.exception("Caught exception when deploying {name} in namespace {namespace}".format(
                    name=application.metadata.name, namespace=application.metadata.namespace))

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
