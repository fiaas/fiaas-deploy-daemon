#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import logging

from k8s.models.autoscaler import HorizontalPodAutoscaler, HorizontalPodAutoscalerSpec, CrossVersionObjectReference
from k8s.models.common import ObjectMeta
from k8s.client import NotFound

LOG = logging.getLogger(__name__)


class AutoscalerDeployer(object):
    def __init__(self):
        self.name = "autoscaler"

    def deploy(self, app_spec, labels):
        if _should_have_autoscaler(app_spec):
            LOG.info("Creating/updating %s for %s", self.name, app_spec.name)
            metadata = ObjectMeta(name=app_spec.name, namespace=app_spec.namespace, labels=labels)
            scale_target_ref = CrossVersionObjectReference(kind=u"Deployment", name=app_spec.name, apiVersion="extensions/v1beta1")
            spec = HorizontalPodAutoscalerSpec(scaleTargetRef=scale_target_ref,
                                               minReplicas=app_spec.autoscaler.min_replicas,
                                               maxReplicas=app_spec.replicas,
                                               targetCPUUtilizationPercentage=app_spec.autoscaler.cpu_threshold_percentage)
            autoscaler = HorizontalPodAutoscaler.get_or_create(metadata=metadata, spec=spec)
            autoscaler.save()
        else:
            try:
                LOG.info("Deleting any pre-existing autoscaler for %s", app_spec.name)
                HorizontalPodAutoscaler.delete(app_spec.name, app_spec.namespace)
            except NotFound:
                pass

    def delete(self, app_spec):
        LOG.info("Deleting autoscaler for %s", app_spec.name)
        try:
            HorizontalPodAutoscaler.delete(app_spec.name, app_spec.namespace)
        except NotFound:
            pass


def _should_have_autoscaler(app_spec):
    if not _autoscaler_enabled(app_spec.autoscaler):
        return False
    if not _enough_replicas_wanted(app_spec):
        LOG.warn("Can't enable autoscaler with only %d max replicas", app_spec.replicas)
        return False
    if not _request_cpu_is_set(app_spec):
        LOG.warn("Can't enable autoscaler without CPU requests")
        return False
    return True


def _autoscaler_enabled(autoscaler):
    return autoscaler.enabled


def _enough_replicas_wanted(app_spec):
    return app_spec.replicas > 1


def _request_cpu_is_set(app_spec):
    return app_spec.resources.requests.cpu is not None
