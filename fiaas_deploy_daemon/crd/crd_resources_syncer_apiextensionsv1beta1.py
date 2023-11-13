# coding: utf-8

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

from k8s.models.common import ObjectMeta
from k8s.models.custom_resource_definition import (
    CustomResourceDefinitionNames,
    CustomResourceDefinitionSpec,
    CustomResourceDefinition,
)

from ..retry import retry_on_upsert_conflict

LOG = logging.getLogger(__name__)


class CrdResourcesSyncerApiextensionsV1Beta1(object):
    @staticmethod
    @retry_on_upsert_conflict
    def _create_or_update(kind, plural, short_names, group):
        name = "%s.%s" % (plural, group)
        metadata = ObjectMeta(name=name)
        names = CustomResourceDefinitionNames(kind=kind, plural=plural, shortNames=short_names)
        spec = CustomResourceDefinitionSpec(group=group, names=names, version="v1")
        definition = CustomResourceDefinition.get_or_create(metadata=metadata, spec=spec)
        definition.save()
        LOG.info("Created or updated CustomResourceDefinition with name %s", name)

    @classmethod
    def update_crd_resources(cls, include_status_in_app):
        cls._create_or_update("Application", "applications", ("app", "fa"), "fiaas.schibsted.io")
        cls._create_or_update(
            "ApplicationStatus", "application-statuses", ("status", "appstatus", "fs"), "fiaas.schibsted.io"
        )
