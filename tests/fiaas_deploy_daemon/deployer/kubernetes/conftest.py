#!/usr/bin/env python
# -*- coding: utf-8

import pytest


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
        'ownerReferences': []
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
