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
import pytest
import mock

from fiaas_deploy_daemon.deployer.kubernetes.owner_references import OwnerReferences


@pytest.helpers.register
def create_metadata(app_name, namespace='default', labels=None, external=None, annotations=None, generation=None):
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
        'ownerReferences': [],
        'finalizers': [],
    }
    if annotations is not None:
        metadata['annotations'] = annotations.copy()

    if external is not None:
        expose_annotations = {'fiaas/expose': str(external).lower()}
        metadata.setdefault('annotations', {}).update(expose_annotations)

    if generation is not None:
        metadata['generation'] = generation
    return metadata


@pytest.fixture
def owner_references():
    return mock.create_autospec(OwnerReferences(), spec_set=True, instance=True)
