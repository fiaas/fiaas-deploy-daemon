#!/usr/bin/env python
# -*- coding: utf-8

import mock
import pytest

from k8s.client import NotFound


@pytest.fixture(autouse=True)
def get():
    with mock.patch("k8s.client.Client.get") as m:
        m.side_effect = NotFound()
        yield m


@pytest.fixture(autouse=True)
def post():
    with mock.patch("k8s.client.Client.post") as m:
        yield m


@pytest.fixture(autouse=True)
def put():
    with mock.patch("k8s.client.Client.put") as m:
        yield m


@pytest.fixture(autouse=True)
def delete():
    with mock.patch("k8s.client.Client.delete") as m:
        yield m


@pytest.helpers.register
def create_metadata(app_name, namespace='default', prometheus=False, labels=None, external=None, annotations=None):
    if not labels:
        labels = {
            'app': app_name,
            'fiaas/version': 'version',
            'fiaas/deployed_by': '1'
        }
    metadata = {
        'labels': labels,
        'namespace': namespace,
        'name': app_name,
    }
    if annotations is not None:
        metadata['annotations'] = annotations

    if external is not None:
        expose_annotations = {'fiaas/expose': str(external).lower()}
        metadata.setdefault('annotations', {}).update(expose_annotations)
    if prometheus:
        prom_annotations = {
            'prometheus.io/port': '8080',
            'prometheus.io/path': '/internal-backstage/prometheus',
            'prometheus.io/scrape': 'true'
        }
        metadata.setdefault('annotations', {}).update(prom_annotations)
    return metadata
