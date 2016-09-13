#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import logging

from k8s.models.common import ObjectMeta
from k8s.models.ingress import Ingress, IngressSpec, IngressRule, HTTPIngressRuleValue, HTTPIngressPath, IngressBackend

LOG = logging.getLogger(__name__)

INGRESS_SUFFIX = {
    "dev": "k8s.dev.finn.no",
    "local": "127.0.0.1.xip.io",
    "test": "127.0.0.1.xip.io",
    "prod": "k8s1-prod1.z01.finn.no",
    # TODO: GKE-prod needs an entry here, but what is it called, and what should the value be?
}


class IngressDeployer(object):
    def __init__(self, config):
        self._target_cluster = config.target_cluster

    def deploy(self, app_spec, labels):
        if self._should_have_ingress(app_spec):
            LOG.info("Creating/updating ingress for %s", app_spec.name)
            annotations = {
                u"fiaas/expose": u"true" if app_spec.host else u"false"
            }
            metadata = ObjectMeta(name=app_spec.name, namespace=app_spec.namespace, labels=labels, annotations=annotations)
            http_ingress_paths = [self._make_http_ingress_path(app_spec, port_spec) for port_spec in app_spec.ports if
                                  port_spec.protocol == u"http"]
            http_ingress_rule = HTTPIngressRuleValue(paths=http_ingress_paths)
            ingress_rule = IngressRule(host=self._make_ingress_host(app_spec), http=http_ingress_rule)
            ingress_spec = IngressSpec(rules=[ingress_rule])
            ingress = Ingress.get_or_create(metadata=metadata, spec=ingress_spec)
            ingress.save()
        else:
            Ingress.delete(app_spec.name, app_spec.namespace)

    def _make_ingress_host(self, app_spec):
        if app_spec.host is None:
            return u"{}.{}".format(app_spec.name, INGRESS_SUFFIX[self._target_cluster])
        host = app_spec.host
        if u"prod" in self._target_cluster:
            return host
        if host == u"www.finn.no":
            return u"{}.finn.no".format(self._target_cluster)
        return u"{}.{}".format(self._target_cluster, host)

    @staticmethod
    def _should_have_ingress(app_spec):
        return any(port.protocol == u"http" for port in app_spec.ports)

    @staticmethod
    def _make_http_ingress_path(app_spec, port_spec):
        backend = IngressBackend(serviceName=app_spec.name, servicePort=port_spec.port)
        http_ingress_path = HTTPIngressPath(path=port_spec.path, backend=backend)
        return http_ingress_path
