#!/usr/bin/env python
# -*- coding: utf-8

# Copyright 2017-2019 The FIAAS Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import absolute_import

import base64
import hashlib
import logging
from itertools import chain

from k8s.client import NotFound
from k8s.base import Equality, Inequality, Exists
from k8s.models.common import ObjectMeta
from k8s.models.ingress import Ingress, IngressSpec, IngressRule, HTTPIngressRuleValue, HTTPIngressPath, IngressBackend, \
    IngressTLS

from fiaas_deploy_daemon.specs.models import IngressItemSpec
from fiaas_deploy_daemon.retry import retry_on_upsert_conflict
from fiaas_deploy_daemon.tools import merge_dicts
from collections import namedtuple

LOG = logging.getLogger(__name__)


class IngressDeployer(object):
    def __init__(self, config, ingress_tls, owner_references):
        self._ingress_suffixes = config.ingress_suffixes
        self._host_rewrite_rules = config.host_rewrite_rules
        self._ingress_tls = ingress_tls
        self._owner_references = owner_references
        self._tls_issuer_type_default = config.tls_certificate_issuer_type_default
        self._tls_issuer_type_overrides = sorted(config.tls_certificate_issuer_type_overrides.iteritems(),
                                                 key=lambda (k, v): len(k), reverse=True)

    def deploy(self, app_spec, labels):
        if self._should_have_ingress(app_spec):
            self._create(app_spec, labels)
        else:
            self._delete_unused(app_spec, labels)

    def delete(self, app_spec):
        LOG.info("Deleting ingresses for %s", app_spec.name)
        try:
            Ingress.delete_list(namespace=app_spec.namespace, labels={"app": Equality(app_spec.name), "fiaas/deployment_id": Exists()})
        except NotFound:
            pass

    def _create(self, app_spec, labels):
        LOG.info("Creating/updating ingresses for %s", app_spec.name)
        custom_labels = merge_dicts(app_spec.labels.ingress, labels)

        ingresses = self._group_ingresses(app_spec)

        LOG.info("Will create %s ingresses", len(ingresses))
        for annotated_ingress in ingresses:
            if len(annotated_ingress.ingress_items) == 0:
                LOG.info("No items, skipping: %s", annotated_ingress)
                continue

            self._create_ingress(app_spec, annotated_ingress, custom_labels)

        self._delete_unused(app_spec, custom_labels)

    def _expand_default_hosts(self, app_spec):
        all_pathmappings = list(_deduplicate_in_order(chain.from_iterable(ingress_item.pathmappings
                                                      for ingress_item in app_spec.ingresses if not ingress_item.annotations)))
        return [IngressItemSpec(host=host, pathmappings=all_pathmappings, annotations=None)
                for host in self._generate_default_hosts(app_spec.name)]

    def _get_issuer_type(self, host):
        for (suffix, issuer_type) in self._tls_issuer_type_overrides:
            if host and (host == suffix or host.endswith("." + suffix)):
                return issuer_type

        return self._tls_issuer_type_default

    def _group_ingresses(self, app_spec):
        ''' Group the ingresses so that those with annotations are individual, and so that those using non-default TLS-issuers
        are separated
        '''
        explicit_host = _has_explicitly_set_host(app_spec.ingresses)
        ingress_items = app_spec.ingresses + self._expand_default_hosts(app_spec)

        AnnotatedIngress = namedtuple("AnnotatedIngress", ["name", "ingress_items", "annotations", "explicit_host", "issuer_type"])
        default_ingress = AnnotatedIngress(name=app_spec.name, ingress_items=[], annotations={},
                                           explicit_host=explicit_host, issuer_type=self._tls_issuer_type_default)
        ingresses = [default_ingress]
        override_issuer_ingresses = {}
        for ingress_item in ingress_items:
            issuer_type = self._get_issuer_type(ingress_item.host)
            next_name = "{}-{}".format(app_spec.name, len(ingresses))
            if ingress_item.annotations:
                annotated_ingresses = AnnotatedIngress(name=next_name, ingress_items=[ingress_item],
                                                       annotations=ingress_item.annotations,
                                                       explicit_host=True, issuer_type=issuer_type)
                ingresses.append(annotated_ingresses)
            elif issuer_type != self._tls_issuer_type_default:
                annotated_ingress = override_issuer_ingresses.setdefault(issuer_type,
                                                                         AnnotatedIngress(name=next_name,
                                                                                          ingress_items=[],
                                                                                          annotations={},
                                                                                          explicit_host=explicit_host,
                                                                                          issuer_type=issuer_type))
                annotated_ingress.ingress_items.append(ingress_item)
            else:
                default_ingress.ingress_items.append(ingress_item)

        ingresses.extend(i for i in override_issuer_ingresses.values())

        return ingresses

    @retry_on_upsert_conflict
    def _create_ingress(self, app_spec, annotated_ingress, labels):
        default_annotations = {
            u"fiaas/expose": u"true" if annotated_ingress.explicit_host else u"false"
        }
        annotations = merge_dicts(app_spec.annotations.ingress, annotated_ingress.annotations, default_annotations)

        metadata = ObjectMeta(name=annotated_ingress.name, namespace=app_spec.namespace, labels=labels,
                              annotations=annotations)

        per_host_ingress_rules = [
            IngressRule(host=self._apply_host_rewrite_rules(ingress_item.host),
                        http=self._make_http_ingress_rule_value(app_spec, ingress_item.pathmappings))
            for ingress_item in annotated_ingress.ingress_items
            if ingress_item.host is not None
        ]
        if annotated_ingress.annotations:
            use_suffixes = False
        else:
            use_suffixes = True

        ingress_spec = IngressSpec(rules=per_host_ingress_rules)

        ingress = Ingress.get_or_create(metadata=metadata, spec=ingress_spec)

        hosts_for_tls = [rule.host for rule in per_host_ingress_rules]
        self._ingress_tls.apply(ingress, app_spec, hosts_for_tls, annotated_ingress.issuer_type, use_suffixes=use_suffixes)
        self._owner_references.apply(ingress, app_spec)
        ingress.save()

    def _delete_unused(self, app_spec, labels):
        filter_labels = [
            ("app", Equality(labels["app"])),
            ("fiaas/deployment_id", Exists()),
            ("fiaas/deployment_id", Inequality(labels["fiaas/deployment_id"]))
        ]
        Ingress.delete_list(namespace=app_spec.namespace, labels=filter_labels)

    def _generate_default_hosts(self, name):
        for suffix in self._ingress_suffixes:
            yield u"{}.{}".format(name, suffix)

    def _apply_host_rewrite_rules(self, host):
        for rule in self._host_rewrite_rules:
            if rule.matches(host):
                return rule.apply(host)
        return host

    def _should_have_ingress(self, app_spec):
        return self._can_generate_host(app_spec) and _has_ingress(app_spec) and _has_http_port(app_spec)

    def _can_generate_host(self, app_spec):
        return len(self._ingress_suffixes) > 0 or _has_explicitly_set_host(app_spec.ingresses)

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


def _has_explicitly_set_host(ingress_items):
    return any(ingress_item.host is not None and not ingress_item.annotations for ingress_item in ingress_items)


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
        self._shortest_suffix = sorted(config.ingress_suffixes, key=len)[0] if config.ingress_suffixes else None
        self.enable_deprecated_tls_entry_per_host = config.enable_deprecated_tls_entry_per_host

    def apply(self, ingress, app_spec, hosts, issuer_type, use_suffixes=True):
        if self._should_have_ingress_tls(app_spec):
            tls_annotations = {}
            if self._cert_issuer or app_spec.ingress_tls.certificate_issuer:
                issuer = app_spec.ingress_tls.certificate_issuer if app_spec.ingress_tls.certificate_issuer else self._cert_issuer
                tls_annotations[issuer_type] = issuer
            else:
                tls_annotations[u"kubernetes.io/tls-acme"] = u"true"
            ingress.metadata.annotations = merge_dicts(
                ingress.metadata.annotations if ingress.metadata.annotations else {},
                tls_annotations
            )

            if self.enable_deprecated_tls_entry_per_host:
                # TODO: DOCD-1846 - Once new certificates has been provisioned, remove the single host entries and
                # associated configuration flag
                ingress.spec.tls = [IngressTLS(hosts=[host], secretName=host) for host in hosts if len(host) < 64]
            else:
                ingress.spec.tls = []

            if use_suffixes:
                # adding app-name to suffixes could result in a host too long to be the common-name of a cert, and
                # as the user doesn't control it we should generate a host we know will fit
                hosts = self._collapse_hosts(app_spec, hosts)

            ingress.spec.tls.append(IngressTLS(hosts=hosts, secretName="{}-ingress-tls".format(ingress.metadata.name)))

    def _collapse_hosts(self, app_spec, hosts):
        """The first hostname in the list will be used as Common Name in the certificate"""
        if self._shortest_suffix:
            try:
                return [self._generate_short_host(app_spec)] + hosts
            except ValueError:
                LOG.error("Failed to generate a short name to use as Common Name")
        return hosts

    def _should_have_ingress_tls(self, app_spec):
        if self._use_ingress_tls == 'disabled' or app_spec.ingress_tls.enabled is False:
            return False
        else:
            return self._use_ingress_tls == 'default_on' or app_spec.ingress_tls.enabled is True

    def _generate_short_host(self, app_spec):
        h = hashlib.sha1()
        h.update(app_spec.name)
        h.update(app_spec.namespace)
        prefix = base64.b32encode(h.digest()).strip("=").lower()
        short_prefix = prefix[:62 - len(self._shortest_suffix)]
        short_name = "{}.{}".format(short_prefix, self._shortest_suffix)
        if len(short_name) > 63 or short_name[0] == ".":
            raise ValueError("Unable to generate a name short enough to be Common Name in certificate")
        return short_name
