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


import base64
import hashlib
import logging
from itertools import chain

from fiaas_deploy_daemon.specs.models import IngressItemSpec, IngressPathMappingSpec
from fiaas_deploy_daemon.tools import merge_dicts
from collections import namedtuple

LOG = logging.getLogger(__name__)


class IngressDeployer(object):
    def __init__(self, config, default_app_spec, ingress_adapter):
        self._default_app_spec = default_app_spec
        self._ingress_suffixes = config.ingress_suffixes
        self._host_rewrite_rules = config.host_rewrite_rules
        self._ingress_adapter = ingress_adapter
        self._tls_issuer_overrides = sorted(
            iter(config.tls_certificate_issuer_overrides.items()), key=lambda k_v: len(k_v[0]), reverse=True
        )
        self._tls_issuer_type_overrides = sorted(
            iter(config.tls_certificate_issuer_type_overrides.items()), key=lambda k_v: len(k_v[0]), reverse=True
        )
        self._tls_issuer_type_default = self._get_issuer_type_default_ingress(config)
        self._tls_issuer_name_default = config.tls_certificate_issuer

    def deploy(self, app_spec, labels):
        if self._should_have_ingress(app_spec):
            self._create(app_spec, labels)
        else:
            self._ingress_adapter.delete_unused(app_spec, labels)

    def delete(self, app_spec):
        LOG.info("Deleting ingresses for %s", app_spec.name)
        self._ingress_adapter.delete_list(app_spec)

    def _create(self, app_spec, labels):
        LOG.info("Creating/updating ingresses for %s", app_spec.name)
        custom_labels = merge_dicts(app_spec.labels.ingress, labels)

        ingresses = self._group_ingresses(app_spec)

        LOG.info("Will create %s ingresses", len(ingresses))
        for annotated_ingress in ingresses:
            if len(annotated_ingress.ingress_items) == 0:
                LOG.info("No items, skipping: %s", annotated_ingress)
                continue

            self._ingress_adapter.create_ingress(app_spec, annotated_ingress, custom_labels)

        self._ingress_adapter.delete_unused(app_spec, custom_labels)

    def _expand_default_hosts(self, app_spec):
        all_pathmappings = list(
            deduplicate_in_order(
                chain.from_iterable(
                    ingress_item.pathmappings for ingress_item in app_spec.ingresses if not ingress_item.annotations
                )
            )
        )

        if not all_pathmappings:
            # no pathmappings were found, build the default ingress
            http_port = self._resolve_http_port(app_spec)
            default_path = self._resolve_default_path()
            all_pathmappings = [IngressPathMappingSpec(path=default_path, port=http_port)]

        return [
            IngressItemSpec(host=host, pathmappings=all_pathmappings, annotations=None)
            for host in self._generate_default_hosts(app_spec.name)
        ]

    @staticmethod
    def _resolve_http_port(app_spec):
        try:
            return next(portspec.port for portspec in app_spec.ports if portspec.name == "http")
        except StopIteration:
            raise ValueError("Cannot find http port mapping in application spec")

    def _resolve_default_path(self):
        default_ingress_item = next(ingress_item for ingress_item in self._default_app_spec().ingresses)
        return next(pathmapping.path for pathmapping in default_ingress_item.pathmappings)

    def _get_issuer_type_default_ingress(self, config):
        for ingress_suffix in self._ingress_suffixes:
            for (suffix, issuer_type) in self._tls_issuer_type_overrides:
                if ingress_suffix and (ingress_suffix == suffix or ingress_suffix.endswith("." + suffix)):
                    return issuer_type

        return config.tls_certificate_issuer_type_default

    def _get_issuer_name_default_ingress(self, app_spec):
        for ingress_suffix in self._ingress_suffixes:
            if ingress_suffix:
                for (suffix, issuer_name) in self._tls_issuer_overrides:
                    if ingress_suffix == suffix or ingress_suffix.endswith("." + suffix):
                        return issuer_name

        return app_spec.ingress_tls.certificate_issuer if app_spec.ingress_tls.certificate_issuer else self._tls_issuer_name_default

    def _get_issuer_type(self, host):
        if host:
            for (suffix, issuer_type) in self._tls_issuer_type_overrides:
                if (host == suffix or host.endswith("." + suffix)):
                    return issuer_type

        return self._tls_issuer_type_default

    def _get_issuer_name(self, host, app_spec):
        if host:
            for (suffix, issuer_name) in self._tls_issuer_overrides:
                if (host == suffix or host.endswith("." + suffix)):
                    return issuer_name

        return app_spec.ingress_tls.certificate_issuer if app_spec.ingress_tls.certificate_issuer else self._tls_issuer_name_default

    def _group_ingresses(self, app_spec):
        """Group the ingresses so that those with annotations are individual, and so that those using non-default TLS-issuers
        are separated
        """
        explicit_host = _has_explicitly_set_host(app_spec.ingresses)
        ingress_items = [
            item._replace(host=self._apply_host_rewrite_rules(item.host)) for item in app_spec.ingresses if item.host
        ]
        ingress_items += self._expand_default_hosts(app_spec)

        AnnotatedIngress = namedtuple(
            "AnnotatedIngress", ["name", "ingress_items", "annotations", "explicit_host", "issuer_type", "issuer_name", "default"]
        )
        tls_issuer_name_default = self._get_issuer_name_default_ingress(app_spec)
        default_ingress = AnnotatedIngress(
            name=app_spec.name,
            ingress_items=[],
            annotations={},
            explicit_host=explicit_host,
            issuer_type=self._tls_issuer_type_default,
            issuer_name=tls_issuer_name_default,
            default=True,
        )
        ingresses = [default_ingress]
        override_issuer_ingresses = {}
        for ingress_item in ingress_items:
            issuer_type = self._get_issuer_type(ingress_item.host)
            issuer_name = self._get_issuer_name(ingress_item.host, app_spec)
            next_name = "{}-{}".format(app_spec.name, len(ingresses) + len(override_issuer_ingresses))
            if ingress_item.annotations:
                annotated_ingresses = AnnotatedIngress(
                    name=next_name,
                    ingress_items=[ingress_item],
                    annotations=ingress_item.annotations,
                    explicit_host=True,
                    issuer_type=issuer_type,
                    issuer_name=issuer_name,
                    default=False,
                )
                ingresses.append(annotated_ingresses)
            elif issuer_type != self._tls_issuer_type_default or issuer_name != tls_issuer_name_default:
                annotated_ingress = override_issuer_ingresses.setdefault(
                    "{}:{}".format(issuer_type, issuer_name),
                    AnnotatedIngress(
                        name=next_name,
                        ingress_items=[],
                        annotations={},
                        explicit_host=explicit_host,
                        issuer_type=issuer_type,
                        issuer_name=issuer_name,
                        default=False,
                    ),
                )
                annotated_ingress.ingress_items.append(ingress_item)
            else:
                default_ingress.ingress_items.append(ingress_item)

        ingresses.extend(i for i in list(override_issuer_ingresses.values()))

        return ingresses

    def _generate_default_hosts(self, name):
        for suffix in self._ingress_suffixes:
            yield "{}.{}".format(name, suffix)

    def _apply_host_rewrite_rules(self, host):
        for rule in self._host_rewrite_rules:
            if rule.matches(host):
                return rule.apply(host)
        return host

    def _should_have_ingress(self, app_spec):
        return self._can_generate_host(app_spec) and _has_ingress(app_spec) and _has_http_port(app_spec)

    def _can_generate_host(self, app_spec):
        return len(self._ingress_suffixes) > 0 or _has_explicitly_set_host(app_spec.ingresses)

    def _get_hosts(self, app_spec):
        return list(self._generate_default_hosts(app_spec.name)) + [
            self._apply_host_rewrite_rules(ingress_item.host)
            for ingress_item in app_spec.ingresses
            if ingress_item.host is not None
        ]


def _has_explicitly_set_host(ingress_items):
    return any(ingress_item.host is not None and not ingress_item.annotations for ingress_item in ingress_items)


def _has_http_port(app_spec):
    return any(port.protocol == "http" for port in app_spec.ports)


def _has_ingress(app_spec):
    return len(app_spec.ingresses) > 0


def deduplicate_in_order(iterator):
    seen = set()
    for item in iterator:
        if item not in seen:
            yield item
            seen.add(item)


class IngressTLSDeployer(object):
    def __init__(self, config, ingress_tls):
        self._use_ingress_tls = config.use_ingress_tls
        self._cert_issuer = config.tls_certificate_issuer
        self._shortest_suffix = sorted(config.ingress_suffixes, key=len)[0] if config.ingress_suffixes else None
        self.enable_deprecated_tls_entry_per_host = config.enable_deprecated_tls_entry_per_host
        self.ingress_tls = ingress_tls

    def apply(self, ingress, app_spec, hosts, issuer_type, issuer_name, use_suffixes=True):
        if self._should_have_ingress_tls(app_spec):
            tls_annotations = {}
            if self._cert_issuer or app_spec.ingress_tls.certificate_issuer:
                tls_annotations[issuer_type] = issuer_name
            else:
                tls_annotations["kubernetes.io/tls-acme"] = "true"
            ingress.metadata.annotations = merge_dicts(
                ingress.metadata.annotations if ingress.metadata.annotations else {}, tls_annotations
            )

            if self.enable_deprecated_tls_entry_per_host:
                # TODO: DOCD-1846 - Once new certificates has been provisioned, remove the single host entries and
                # associated configuration flag
                ingress.spec.tls = [self.ingress_tls(hosts=[host], secretName=host) for host in hosts if len(host) < 64]
            else:
                ingress.spec.tls = []

            if use_suffixes:
                # adding app-name to suffixes could result in a host too long to be the common-name of a cert, and
                # as the user doesn't control it we should generate a host we know will fit
                hosts = self._collapse_hosts(app_spec, hosts)

            ingress.spec.tls.append(
                self.ingress_tls(hosts=hosts, secretName="{}-ingress-tls".format(ingress.metadata.name))
            )

    def _collapse_hosts(self, app_spec, hosts):
        """The first hostname in the list will be used as Common Name in the certificate"""
        if self._shortest_suffix:
            try:
                return [self._generate_short_host(app_spec)] + hosts
            except ValueError:
                LOG.error("Failed to generate a short name to use as Common Name")
        return hosts

    def _should_have_ingress_tls(self, app_spec):
        if self._use_ingress_tls == "disabled" or app_spec.ingress_tls.enabled is False:
            return False
        else:
            return self._use_ingress_tls == "default_on" or app_spec.ingress_tls.enabled is True

    def _generate_short_host(self, app_spec):
        h = hashlib.sha1()
        h.update(app_spec.name.encode("utf-8"))
        h.update(app_spec.namespace.encode("utf-8"))
        prefix = base64.b32encode(h.digest()).decode("utf-8").strip("=").lower()
        short_prefix = prefix[: 62 - len(self._shortest_suffix)]
        short_name = "{}.{}".format(short_prefix, self._shortest_suffix)
        if len(short_name) > 63 or short_name[0] == ".":
            raise ValueError("Unable to generate a name short enough to be Common Name in certificate")
        return short_name
