#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import logging

from k8s.client import NotFound
from k8s.models.common import ObjectMeta
from k8s.models.service import Service, ServicePort, ServiceSpec

LOG = logging.getLogger(__name__)


class ServiceDeployer(object):
    def __init__(self, config):
        self._service_type = config.service_type

    def deploy(self, app_spec, selector, labels):
        LOG.info("Creating/updating service for %s with labels: %s", app_spec.name, labels)
        ports = [self._make_service_port(port_spec) for port_spec in app_spec.ports]
        try:
            svc = Service.get(app_spec.name, app_spec.namespace)
            ports = self._merge_ports(svc.spec.ports, ports)
        except NotFound:
            pass
        service_name = app_spec.name
        custom_labels = app_spec.labels.get("service", {})
        custom_labels.update(labels)
        custom_annotations = app_spec.annotations.get("service", {})
        custom_annotations.update(self._make_tcp_port_annotation(app_spec))
        metadata = ObjectMeta(name=service_name, namespace=app_spec.namespace, labels=labels, annotations=custom_annotations)
        spec = ServiceSpec(selector=selector, ports=ports, type=self._service_type)
        svc = Service.get_or_create(metadata=metadata, spec=spec)
        svc.save()

    def delete(self, app_spec):
        LOG.info("Deleting service for %s", app_spec.name)
        try:
            Service.delete(app_spec.name, app_spec.namespace)
        except NotFound:
            pass

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
        return ServicePort(
            protocol='TCP',
            name=port_spec.name,
            port=port_spec.port,
            targetPort=port_spec.target_port)

    @staticmethod
    def _make_tcp_port_annotation(app_spec):
        tcp_port_names = [port_spec.name for port_spec in app_spec.ports
                          if port_spec.protocol == u"tcp"]
        return {
            'fiaas/tcp_port_names': ','.join(map(str, tcp_port_names))
        } if tcp_port_names else {}
