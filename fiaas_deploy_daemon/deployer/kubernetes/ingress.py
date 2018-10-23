#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import logging
from itertools import chain

from k8s.client import NotFound
from k8s.models.common import ObjectMeta
from k8s.models.ingress import Ingress, IngressSpec, IngressRule, HTTPIngressRuleValue, HTTPIngressPath, IngressBackend, \
    IngressTLS

from fiaas_deploy_daemon.tools import merge_dicts

LOG = logging.getLogger(__name__)


class IngressDeployer(object):
    def __init__(self, config, ingress_tls):
        self._ingress_suffixes = config.ingress_suffixes
        self._host_rewrite_rules = config.host_rewrite_rules
        self._ingress_tls = ingress_tls

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
            u"fiaas/expose": u"true" if _has_explicitly_set_host(app_spec) else u"false"
        }

        custom_labels = merge_dicts(app_spec.labels.ingress, labels)
        custom_annotations = merge_dicts(app_spec.annotations.ingress, annotations)
        metadata = ObjectMeta(name=app_spec.name, namespace=app_spec.namespace, labels=custom_labels,
                              annotations=custom_annotations)

        per_host_ingress_rules = [
            IngressRule(host=self._apply_host_rewrite_rules(ingress_item.host),
                        http=self._make_http_ingress_rule_value(app_spec, ingress_item.pathmappings))
            for ingress_item in app_spec.ingresses
            if ingress_item.host is not None
        ]
        default_host_ingress_rules = self._create_default_host_ingress_rules(app_spec)

        ingress_spec = IngressSpec(rules=per_host_ingress_rules + default_host_ingress_rules)

        ingress = Ingress.get_or_create(metadata=metadata, spec=ingress_spec)
        self._ingress_tls.apply(ingress, app_spec, self._get_hosts(app_spec))
        ingress.save()

    def _generate_default_hosts(self, name):
        for suffix in self._ingress_suffixes:
            yield u"{}.{}".format(name, suffix)

    def _create_default_host_ingress_rules(self, app_spec):
        all_pathmappings = chain.from_iterable(ingress_item.pathmappings for ingress_item in app_spec.ingresses)
        http_ingress_rule_value = self._make_http_ingress_rule_value(app_spec, all_pathmappings)
        return [IngressRule(host=host, http=http_ingress_rule_value)
                for host in self._generate_default_hosts(app_spec.name)]

    def _apply_host_rewrite_rules(self, host):
        for rule in self._host_rewrite_rules:
            if rule.matches(host):
                return rule.apply(host)
        return host

    def _should_have_ingress(self, app_spec):
        return self._can_generate_host(app_spec) and _has_ingress(app_spec) and _has_http_port(app_spec)

    def _can_generate_host(self, app_spec):
        return len(self._ingress_suffixes) > 0 or _has_explicitly_set_host(app_spec)

    @staticmethod
    def _make_http_ingress_rule_value(app_spec, pathmappings):
        http_ingress_paths = [
            HTTPIngressPath(path=pm.path, backend=IngressBackend(serviceName=app_spec.name, servicePort=pm.port))
            for pm in _deduplicate_in_order(pathmappings)]

        return HTTPIngressRuleValue(paths=http_ingress_paths)

    def _get_hosts(self, app_spec):
        return list(self._generate_default_hosts(app_spec.name)) + \
               [self._apply_host_rewrite_rules(ingress_item.host)
                for ingress_item in app_spec.ingresses if ingress_item.host is not None]


def _has_explicitly_set_host(app_spec):
    return any(ingress.host is not None for ingress in app_spec.ingresses)


def _has_http_port(app_spec):
    return any(port.protocol == u"http" for port in app_spec.ports)


def _has_ingress(app_spec):
    return len(app_spec.ingresses) > 0


def _deduplicate_in_order(iterator):
    seen = set()
    for item in iterator:
        if item not in seen:
            yield item
            seen.add(item)


class IngressTls(object):
    def __init__(self, config):
        self._use_ingress_tls = config.use_ingress_tls
        self._cert_issuer = config.tls_certificate_issuer

    def apply(self, ingress, app_spec, hosts):
        if self._should_have_ingress_tls(app_spec):
            tls_annotations = {}
            if self._cert_issuer or app_spec.ingress_tls.certificate_issuer:
                issuer = app_spec.ingress_tls.certificate_issuer if app_spec.ingress_tls.certificate_issuer else self._cert_issuer
                tls_annotations[u"certmanager.k8s.io/cluster-issuer"] = issuer
            else:
                tls_annotations[u"kubernetes.io/tls-acme"] = u"true"
            ingress.metadata.annotations = merge_dicts(
                ingress.metadata.annotations if ingress.metadata.annotations else {},
                tls_annotations
            )
            ingress.spec.tls = [IngressTLS(hosts=hosts, secretName="{}-ingress-tls".format(app_spec.name))]

    def _should_have_ingress_tls(self, app_spec):
        if self._use_ingress_tls == 'disabled' or app_spec.ingress_tls.enabled is False:
            return False
        else:
            return self._use_ingress_tls == 'default_on' or app_spec.ingress_tls.enabled is True
