#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import
import logging
from k8s.models.common import ObjectMeta
from k8s.models.ingress import Ingress, IngressSpec, IngressRule, HTTPIngressRuleValue, HTTPIngressPath, IngressBackend
from k8s.client import NotFound


LOG = logging.getLogger(__name__)


class IngressDeployer(object):
    def __init__(self, config):
        self._environment = config.environment
        self._infrastructure = config.infrastructure
        self._ingress_suffixes = config.ingress_suffixes
        self._host_rewrite_rules = config.host_rewrite_rules

    def deploy(self, app_spec, labels):
        if self._should_have_ingress(app_spec):
            self._create(app_spec, labels)
        else:
            self.delete(app_spec)

    def delete(self, app_spec):
        LOG.info("Deleting ingress for %s", app_spec.name)
        try:
            Ingress.delete(app_spec.name, app_spec.namespace)
        except NotFound:
            pass

    def _create(self, app_spec, labels):
        LOG.info("Creating/updating ingress for %s", app_spec.name)
        annotations = {
            u"fiaas/expose": u"true" if app_spec.host else u"false"
        }
        metadata = ObjectMeta(name=app_spec.name, namespace=app_spec.namespace, labels=labels,
                              annotations=annotations)
        http_ingress_paths = [self._make_http_ingress_path(app_spec, port_spec) for port_spec in app_spec.ports if
                              port_spec.protocol == u"http"]
        http_ingress_rule = HTTPIngressRuleValue(paths=http_ingress_paths)
        ingress_rules = [IngressRule(host=host, http=http_ingress_rule) for host in self._generate_hosts(app_spec)]
        ingress_spec = IngressSpec(rules=ingress_rules)
        ingress = Ingress.get_or_create(metadata=metadata, spec=ingress_spec)
        ingress.save()

    def _generate_hosts(self, app_spec):
        if app_spec.host:
            yield self._make_ingress_host(app_spec)
        for suffix in self._ingress_suffixes:
            yield u"{}.{}".format(app_spec.name, suffix)

    def _make_ingress_host(self, app_spec):
        host = app_spec.host
        for rule in self._host_rewrite_rules:
            if rule.matches(host):
                return rule.apply(host)
        return host

    @staticmethod
    def _should_have_ingress(app_spec):
        return any(port.protocol == u"http" for port in app_spec.ports)

    @staticmethod
    def _make_http_ingress_path(app_spec, port_spec):
        backend = IngressBackend(serviceName=app_spec.name, servicePort=port_spec.port)
        http_ingress_path = HTTPIngressPath(path=port_spec.path, backend=backend)
        return http_ingress_path
