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
from k8s.models.apiextensions_v1_custom_resource_definition import (
    CustomResourceConversion,
    CustomResourceDefinitionNames,
    CustomResourceDefinitionSpec,
    CustomResourceDefinition,
    CustomResourceDefinitionVersion,
    CustomResourceValidation,
    JSONSchemaProps,
)

from ..retry import retry_on_upsert_conflict

LOG = logging.getLogger(__name__)


class CrdResourcesSyncerApiextensionsV1(object):
    @staticmethod
    @retry_on_upsert_conflict
    def _create_or_update(kind, plural, short_names, group, schema_properties):
        name = "%s.%s" % (plural, group)
        metadata = ObjectMeta(name=name)
        names = CustomResourceDefinitionNames(kind=kind, plural=plural, shortNames=short_names)
        open_apiv3_schema = JSONSchemaProps(type="object", properties=schema_properties)
        schema = CustomResourceValidation(openAPIV3Schema=open_apiv3_schema)
        version_v1 = CustomResourceDefinitionVersion(name="v1", served=True, storage=True, schema=schema)
        spec = CustomResourceDefinitionSpec(
            group=group,
            names=names,
            versions=[version_v1],
            preserveUnknownFields=False,
            scope="Namespaced",
            conversion=CustomResourceConversion(strategy="None"),
        )
        definition = CustomResourceDefinition.get_or_create(metadata=metadata, spec=spec)
        definition.save()
        LOG.info("Created or updated CustomResourceDefinition with name %s", name)

    @classmethod
    def update_crd_resources(cls):
        object_with_unknown_fields = {"type": "object", "x-kubernetes-preserve-unknown-fields": True}
        application_schema_properties = {
            "spec": {
                "type": "object",
                "properties": {
                    "application": {
                        "type": "string",
                    },
                    "image": {
                        "type": "string",
                    },
                    "config": object_with_unknown_fields,
                    "additional_labels": {
                        "type": "object",
                        "properties": {
                            "global": object_with_unknown_fields,
                            "deployment": object_with_unknown_fields,
                            "horizontal_pod_autoscaler": object_with_unknown_fields,
                            "ingress": object_with_unknown_fields,
                            "service": object_with_unknown_fields,
                            "service_account": object_with_unknown_fields,
                            "pod": object_with_unknown_fields,
                            "status": object_with_unknown_fields,
                        },
                    },
                    "additional_annotations": {
                        "type": "object",
                        "properties": {
                            "global": object_with_unknown_fields,
                            "deployment": object_with_unknown_fields,
                            "horizontal_pod_autoscaler": object_with_unknown_fields,
                            "ingress": object_with_unknown_fields,
                            "service": object_with_unknown_fields,
                            "service_account": object_with_unknown_fields,
                            "pod": object_with_unknown_fields,
                            "status": object_with_unknown_fields,
                        },
                    },
                }
            },
            "status": {
                "type": "object",
                "properties": {
                    "result": {
                        "type": "string"
                    },
                    "observedGeneration": {
                        "type": "integer"
                    },
                    "logs": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        }
                    },
                    "deployment_id": {
                        "type": "string"
                    }
                }
            }
        }
        application_status_schema_properties = {
            "result": {"type": "string"},
            "logs": {"type": "array", "items": {"type": "string"}},
        }
        cls._create_or_update(
            "Application", "applications", ("app", "fa"), "fiaas.schibsted.io", application_schema_properties
        )
        cls._create_or_update(
            "ApplicationStatus",
            "application-statuses",
            ("status", "appstatus", "fs"),
            "fiaas.schibsted.io",
            application_status_schema_properties,
        )
