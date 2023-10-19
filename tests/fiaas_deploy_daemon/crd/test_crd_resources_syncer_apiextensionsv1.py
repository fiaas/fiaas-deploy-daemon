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


from unittest import mock
from requests import Response

from k8s.client import NotFound

from fiaas_deploy_daemon.crd.crd_resources_syncer_apiextensionsv1 import CrdResourcesSyncerApiextensionsV1


object_with_unknown_fields = {"type": "object", "x-kubernetes-preserve-unknown-fields": True}


EXPECTED_APPLICATION = {
    "metadata": {
        "namespace": "default",
        "name": "applications.fiaas.schibsted.io",
        "ownerReferences": [],
        "finalizers": [],
    },
    "spec": {
        "group": "fiaas.schibsted.io",
        "names": {"shortNames": ["app", "fa"], "kind": "Application", "plural": "applications", "categories": []},
        "preserveUnknownFields": False,
        "scope": "Namespaced",
        "conversion": {"strategy": "None"},
        "versions": [
            {
                "additionalPrinterColumns": [],
                "name": "v1",
                "served": True,
                "storage": True,
                "subresources": {
                    "status": {
                        "foo": "bar"
                    }
                },
                "schema": {
                    "openAPIV3Schema": {
                        "type": "object",
                        "properties": {
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
                                },
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
                        },
                        "oneOf": [],
                        "allOf": [],
                        "required": [],
                        "x-kubernetes-list-map-keys": [],
                        "anyOf": [],
                    }
                },
            }
        ],
    },
}


EXPECTED_STATUS = {
    "metadata": {
        "namespace": "default",
        "name": "application-statuses.fiaas.schibsted.io",
        "ownerReferences": [],
        "finalizers": [],
    },
    "spec": {
        "group": "fiaas.schibsted.io",
        "names": {
            "shortNames": ["status", "appstatus", "fs"],
            "kind": "ApplicationStatus",
            "plural": "application-statuses",
            "categories": [],
        },
        "preserveUnknownFields": False,
        "scope": "Namespaced",
        "conversion": {"strategy": "None"},
        "versions": [
            {
                "additionalPrinterColumns": [],
                "name": "v1",
                "served": True,
                "storage": True,
                "schema": {
                    "openAPIV3Schema": {
                        "type": "object",
                        "properties": {
                            "result": {"type": "string"},
                            "logs": {"type": "array", "items": {"type": "string"}},
                        },
                        "oneOf": [],
                        "allOf": [],
                        "required": [],
                        "x-kubernetes-list-map-keys": [],
                        "anyOf": [],
                    }
                },
            }
        ],
    },
}


class TestCrdResourcesSyncerV1(object):
    def test_creates_crd_resources_when_not_found(self, post, get):
        get.side_effect = NotFound("Something")

        def make_response(data):
            mock_response = mock.create_autospec(Response)
            mock_response.json.return_value = data
            return mock_response

        post.side_effect = [make_response(EXPECTED_APPLICATION), make_response(EXPECTED_STATUS)]

        CrdResourcesSyncerApiextensionsV1.update_crd_resources()

        calls = [
            mock.call("/apis/apiextensions.k8s.io/v1/customresourcedefinitions/", EXPECTED_APPLICATION),
            mock.call("/apis/apiextensions.k8s.io/v1/customresourcedefinitions/", EXPECTED_STATUS),
        ]
        assert post.call_args_list == calls

    def test_updates_crd_resources_when_found(self, put, get):
        def make_response(data):
            mock_response = mock.create_autospec(Response)
            mock_response.json.return_value = data
            return mock_response

        get.side_effect = [make_response(EXPECTED_APPLICATION), make_response(EXPECTED_STATUS)]
        put.side_effect = [make_response(EXPECTED_APPLICATION), make_response(EXPECTED_STATUS)]

        CrdResourcesSyncerApiextensionsV1.update_crd_resources()

        calls = [
            mock.call(
                "/apis/apiextensions.k8s.io/v1/customresourcedefinitions/applications.fiaas.schibsted.io",
                EXPECTED_APPLICATION,
            ),
            mock.call(
                "/apis/apiextensions.k8s.io/v1/customresourcedefinitions/application-statuses.fiaas.schibsted.io",
                EXPECTED_STATUS,
            ),
        ]
        assert put.call_args_list == calls
