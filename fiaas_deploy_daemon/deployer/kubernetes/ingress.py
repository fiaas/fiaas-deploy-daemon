#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import
import logging
from k8s.models.common import ObjectMeta
from k8s.models.ingress import Ingress, IngressSpec, IngressRule, HTTPIngressRuleValue, HTTPIngressPath, IngressBackend
from k8s.client import NotFound


LOG = logging.getLogger(__name__)

# These are infrastructure suffixes, those should only be used in the
# unusual case that you care about exactly what infrastructure you are
# hitting.
INGRESS_SUFFIX = {
    u"diy": {
        u"local": u"127.0.0.1.xip.io",
        u"test": u"127.0.0.1.xip.io",
        u"dev": u"k8s.dev.finn.no",
        u"prod": u"k8s1-prod1.z01.finn.no",
    },
    u"gke": {
        u"dev": u"k8s-gke.dev.finn.no",
        u"prod": u"k8s-gke.prod.finn.no"
    }
}

# These are service plane suffixes, they should be the preferred names
# for consumers of various services.
SVC_INGRESS_SUFFIX = {
    u"dev": u"svc.dev.finn.no",
    u"prod": u"svc.prod.finn.no",
}


class IngressDeployer(object):
    def __init__(self, config):
        self._environment = config.environment
        self._infrastructure = config.infrastructure

    def deploy(self, app_spec, labels):
        if self._should_have_ingress(app_spec):
            LOG.info("Creating/updating ingress for %s", app_spec.name)
            annotations = {
                u"fiaas/expose": u"true" if app_spec.host else u"false"
            }
            metadata = ObjectMeta(name=app_spec.name, namespace=app_spec.namespace, labels=labels,
                                  annotations=annotations)
            http_ingress_paths = [self._make_http_ingress_path(app_spec, port_spec) for port_spec in app_spec.ports if
                                  port_spec.protocol == u"http"]
            http_ingress_rule = HTTPIngressRuleValue(paths=http_ingress_paths)
            ingress_rule_infra = IngressRule(host=self._make_ingress_host(app_spec), http=http_ingress_rule)
            ingress_rules = [ingress_rule_infra]
            ingress_rule_service_host = self._make_ingress_service_host(app_spec)
            if ingress_rule_service_host is not None:
                ingress_rules.append(IngressRule(host=ingress_rule_service_host, http=http_ingress_rule))
            if self._infrastructure == 'gke' and self._environment == 'dev' and app_spec.host is None:
                ingress_rules.append(IngressRule(host=u"{}.{}".format(app_spec.name, INGRESS_SUFFIX['diy']['dev']),
                                                 http=http_ingress_rule))
            ingress_spec = IngressSpec(rules=ingress_rules)
            ingress = Ingress.get_or_create(metadata=metadata, spec=ingress_spec)
            ingress.save()
        else:
            try:
                Ingress.delete(app_spec.name, app_spec.namespace)
            except NotFound:
                pass

    def _make_ingress_host(self, app_spec):
        if app_spec.host is None:
            return u"{}.{}".format(app_spec.name, INGRESS_SUFFIX[self._infrastructure][self._environment])
        host = app_spec.host
        if u"prod" == self._environment:
            return host
        if host == u"www.finn.no":
            return u"{}.finn.no".format(self._environment)
        return u"{}.{}".format(self._environment, host)

    def _make_ingress_service_host(self, app_spec):
        if app_spec.host is None and self._environment in SVC_INGRESS_SUFFIX:
            return u"{}.{}".format(app_spec.name, SVC_INGRESS_SUFFIX[self._environment])
        return None

    @staticmethod
    def _should_have_ingress(app_spec):
        return any(port.protocol == u"http" for port in app_spec.ports)

    @staticmethod
    def _make_http_ingress_path(app_spec, port_spec):
        backend = IngressBackend(serviceName=app_spec.name, servicePort=port_spec.port)
        http_ingress_path = HTTPIngressPath(path=port_spec.path, backend=backend)
        return http_ingress_path
