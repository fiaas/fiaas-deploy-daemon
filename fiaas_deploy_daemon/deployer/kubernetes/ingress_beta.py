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

from k8s.client import NotFound
from k8s.models.common import ObjectMeta
from k8s.models.ingress import Ingress, IngressSpec, IngressRule, HTTPIngressRuleValue, HTTPIngressPath, IngressBackend
from k8s.base import Equality, Inequality, Exists

from fiaas_deploy_daemon.retry import retry_on_upsert_conflict
from fiaas_deploy_daemon.tools import merge_dicts

from .ingress import deduplicate_in_order


class BetaIngressAdapter(object):
    def __init__(self, ingress_tls_deployer, owner_references, extension_hook):
        self._ingress_tls_deployer = ingress_tls_deployer
        self._owner_references = owner_references
        self._extension_hook = extension_hook

    @retry_on_upsert_conflict
    def create_ingress(self, app_spec, annotated_ingress, labels):
        default_annotations = {
            u"fiaas/expose": u"true" if annotated_ingress.explicit_host else u"false"
        }
        annotations = merge_dicts(app_spec.annotations.ingress, annotated_ingress.annotations, default_annotations)

        metadata = ObjectMeta(name=annotated_ingress.name, namespace=app_spec.namespace, labels=labels,
                              annotations=annotations)

        per_host_ingress_rules = [
            IngressRule(host=ingress_item.host, http=self._make_http_ingress_rule_value(app_spec, ingress_item.pathmappings))
            for ingress_item in annotated_ingress.ingress_items if ingress_item.host is not None
        ]
        if annotated_ingress.default:
            use_suffixes = True
        else:
            use_suffixes = False

        ingress_spec = IngressSpec(rules=per_host_ingress_rules)

        ingress = Ingress.get_or_create(metadata=metadata, spec=ingress_spec)

        hosts_for_tls = [rule.host for rule in per_host_ingress_rules]
        self._ingress_tls_deployer.apply(ingress, app_spec, hosts_for_tls, annotated_ingress.issuer_type, use_suffixes=use_suffixes)
        self._owner_references.apply(ingress, app_spec)
        self._extension_hook.apply(ingress, app_spec)
        ingress.save()

    def delete_unused(self, app_spec, labels):
        filter_labels = [
            ("app", Equality(labels["app"])),
            ("fiaas/deployment_id", Exists()),
            ("fiaas/deployment_id", Inequality(labels["fiaas/deployment_id"]))
        ]
        Ingress.delete_list(namespace=app_spec.namespace, labels=filter_labels)

    def delete_list(self, app_spec):
        try:
            Ingress.delete_list(namespace=app_spec.namespace,
                                labels={"app": Equality(app_spec.name), "fiaas/deployment_id": Exists()})
        except NotFound:
            pass

    def _make_http_ingress_rule_value(self, app_spec, pathmappings):
        http_ingress_paths = [
            HTTPIngressPath(path=pm.path, backend=IngressBackend(serviceName=app_spec.name, servicePort=pm.port))
            for pm in deduplicate_in_order(pathmappings)]

        return HTTPIngressRuleValue(paths=http_ingress_paths)
