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


import logging

from k8s.client import NotFound
from k8s.models.common import ObjectMeta
from k8s.models.service import Service, ServicePort, ServiceSpec

from fiaas_deploy_daemon.retry import retry_on_upsert_conflict
from fiaas_deploy_daemon.tools import merge_dicts


LOG = logging.getLogger(__name__)


class ServiceDeployer(object):
    def __init__(self, config, owner_references, extension_hook):
        self._service_type = config.service_type
        self._owner_references = owner_references
        self._extension_hook = extension_hook

    def deploy(self, app_spec, selector, labels):
        if self._should_have_service(app_spec):
            self._create(app_spec, selector, labels)
        else:
            self._delete(app_spec)

    def _delete(self, app_spec):
        LOG.info("Deleting service for %s", app_spec.name)
        try:
            Service.delete(app_spec.name, app_spec.namespace)
        except NotFound:
            pass

    @retry_on_upsert_conflict
    def _create(self, app_spec, selector, labels):
        LOG.info("Creating/updating service for %s with labels: %s", app_spec.name, labels)
        ports = [self._make_service_port(port_spec) for port_spec in app_spec.ports]
        try:
            svc = Service.get(app_spec.name, app_spec.namespace)
            ports = self._merge_ports(svc.spec.ports, ports)
        except NotFound:
            pass
        service_name = app_spec.name
        custom_labels = merge_dicts(app_spec.labels.service, labels)
        custom_annotations = merge_dicts(app_spec.annotations.service, self._make_tcp_port_annotation(app_spec))
        metadata = ObjectMeta(
            name=service_name, namespace=app_spec.namespace, labels=custom_labels, annotations=custom_annotations
        )
        spec = ServiceSpec(selector=selector, ports=ports, type=self._service_type)
        svc = Service.get_or_create(metadata=metadata, spec=spec)
        self._owner_references.apply(svc, app_spec)
        self._extension_hook.apply(svc, app_spec)
        svc.save()

    @staticmethod
    def _merge_ports(existing_ports, wanted_ports):
        existing = {port.name: port for port in existing_ports}
        for port in wanted_ports:
            existing_port = existing.get(port.name)
            if existing_port:
                port.nodePort = existing_port.nodePort
        return wanted_ports

    @staticmethod
    def _make_service_port(port_spec):
        return ServicePort(protocol="TCP", name=port_spec.name, port=port_spec.port, targetPort=port_spec.target_port)

    @staticmethod
    def _make_tcp_port_annotation(app_spec):
        tcp_port_names = [port_spec.name for port_spec in app_spec.ports if port_spec.protocol == "tcp"]
        return {"fiaas/tcp_port_names": ",".join(map(str, tcp_port_names))} if tcp_port_names else {}

    @staticmethod
    def _should_have_service(app_spec):
        return len(app_spec.ports) > 0
