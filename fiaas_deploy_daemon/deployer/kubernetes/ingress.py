#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import logging

from k8s.models.common import ObjectMeta
from k8s.models.ingress import Ingress, IngressSpec, IngressRule, HTTPIngressRuleValue, HTTPIngressPath, IngressBackend

LOG = logging.getLogger(__name__)


class IngressDeployer(object):
    def __init__(self, config):
        self._target_cluster = config.target_cluster

    def deploy(self, app_spec, labels):
        if app_spec.host:
            LOG.info("Creating/updating ingress for %s", app_spec.name)
            metadata = ObjectMeta(name=app_spec.name, namespace=app_spec.namespace, labels=labels)
            http_ingress_paths = [self._make_http_ingress_path(app_spec, port_spec) for port_spec in app_spec.ports if
                                  port_spec.protocol == u"http"]
            http_ingress_rule = HTTPIngressRuleValue(paths=http_ingress_paths)
            ingress_rule = IngressRule(host=self._make_ingress_host(app_spec.host), http=http_ingress_rule)
            ingress_spec = IngressSpec(rules=[ingress_rule])
            ingress = Ingress.get_or_create(metadata=metadata, spec=ingress_spec)
            ingress.save()
        else:
            Ingress.delete(app_spec.name, app_spec.namespace)

    def _make_ingress_host(self, host):
        if "prod" in self._target_cluster:
            return host
        if host == "www.finn.no":
            return "{}.finn.no".format(self._target_cluster)
        return "{}.{}".format(self._target_cluster, host)

    @staticmethod
    def _make_http_ingress_path(app_spec, port_spec):
        backend = IngressBackend(serviceName=app_spec.name, servicePort=port_spec.port)
        http_ingress_path = HTTPIngressPath(path=port_spec.path, backend=backend)
        return http_ingress_path
