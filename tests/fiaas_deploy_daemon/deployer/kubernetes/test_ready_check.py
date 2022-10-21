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

from datetime import datetime, timedelta
from unittest import mock
import pytest
from time import monotonic as time_monotonic

from fiaas_deploy_daemon.deployer.bookkeeper import Bookkeeper
from fiaas_deploy_daemon.deployer.kubernetes.ingress_v1beta1 import V1Beta1IngressAdapter
from fiaas_deploy_daemon.config import Configuration
from fiaas_deploy_daemon.deployer.kubernetes.ready_check import ReadyCheck
from fiaas_deploy_daemon.lifecycle import Lifecycle, Subject
from fiaas_deploy_daemon.specs.models import LabelAndAnnotationSpec, IngressTLSSpec
from k8s.models.certificate import Certificate, CertificateCondition
from k8s.models.ingress import Ingress, IngressTLS
from k8s.models.networking_v1_ingress import Ingress as V1Ingress, IngressTLS as V1IngressTLS

REPLICAS = 2


class TestReadyCheck(object):
    @pytest.fixture
    def bookkeeper(self):
        return mock.create_autospec(Bookkeeper, spec_set=True)

    @pytest.fixture
    def lifecycle(self):
        return mock.create_autospec(Lifecycle, spec_set=True)

    @pytest.fixture
    def lifecycle_subject(self, app_spec):
        return Subject(app_spec.uid, app_spec.name, app_spec.namespace, app_spec.deployment_id, None,
                       app_spec.labels.status, app_spec.annotations.status)

    @pytest.fixture
    def config(self):
        return Configuration([])

    @pytest.fixture
    def ingress_adapter(self):
        return mock.create_autospec(V1Beta1IngressAdapter)

    @pytest.fixture
    def get_cert(self):
        with mock.patch("k8s.models.certificate.Certificate.get") as get_cert:
            yield get_cert

    @pytest.mark.parametrize("generation,observed_generation", (
            (0, 0),
            (0, 1)
    ))
    def test_deployment_complete(self, get, app_spec, bookkeeper, generation, observed_generation, lifecycle,
                                 lifecycle_subject, ingress_adapter, config):
        self._create_response(get, generation=generation, observed_generation=observed_generation)
        ready = ReadyCheck(app_spec, bookkeeper, lifecycle, lifecycle_subject, ingress_adapter, config)

        assert ready() is False
        bookkeeper.success.assert_called_with(app_spec)
        bookkeeper.failed.assert_not_called()
        lifecycle.success.assert_called_with(lifecycle_subject)
        lifecycle.failed.assert_not_called()

    @pytest.mark.parametrize("requested,replicas,available,updated,generation,observed_generation", (
            (8, 9, 7, 2, 0, 0),
            (2, 2, 1, 2, 0, 0),
            (2, 2, 2, 1, 0, 0),
            (2, 1, 1, 1, 0, 0),
            (1, 2, 1, 1, 0, 0),
            (2, 2, 2, 2, 1, 0),
    ))
    def test_deployment_incomplete(self, get, app_spec, bookkeeper, requested, replicas, available, updated,
                                   generation, observed_generation, lifecycle, lifecycle_subject, ingress_adapter,
                                   config):
        self._create_response(get, requested, replicas, available, updated, generation, observed_generation)
        ready = ReadyCheck(app_spec, bookkeeper, lifecycle, lifecycle_subject, ingress_adapter, config)

        assert ready() is True
        bookkeeper.success.assert_not_called()
        bookkeeper.failed.assert_not_called()
        lifecycle.success.assert_not_called()
        lifecycle.failed.assert_not_called()

    @pytest.mark.parametrize("requested,replicas,available,updated,annotations,repository", (
            (8, 9, 7, 2, None, None),
            (2, 2, 1, 2, None, None),
            (2, 2, 2, 1, None, None),
            (2, 1, 1, 1, None, None),
            (2, 1, 1, 1, {"fiaas/source-repository": "xyz"}, "xyz"),
    ))
    def test_deployment_failed(self, get, app_spec, bookkeeper, requested, replicas, available, updated,
                               lifecycle, lifecycle_subject, annotations, repository, ingress_adapter, config):
        if annotations:
            app_spec = app_spec._replace(annotations=LabelAndAnnotationSpec(*[annotations] * 7))

        self._create_response(get, requested, replicas, available, updated)

        ready = ReadyCheck(app_spec, bookkeeper, lifecycle, lifecycle_subject, ingress_adapter, config)
        ready._fail_after = time_monotonic()

        assert ready() is False
        bookkeeper.success.assert_not_called()
        bookkeeper.failed.assert_called_with(app_spec)
        lifecycle.success.assert_not_called()
        lifecycle.failed.assert_called_with(lifecycle_subject)

    def test_deployment_complete_deactivated(self, get, app_spec, bookkeeper, lifecycle, lifecycle_subject,
                                             ingress_adapter, config):

        self._create_response_zero_replicas(get)
        ready = ReadyCheck(app_spec, bookkeeper, lifecycle, lifecycle_subject, ingress_adapter, config)

        assert ready() is False
        bookkeeper.success.assert_called_with(app_spec)
        bookkeeper.failed.assert_not_called()
        lifecycle.success.assert_called_with(lifecycle_subject)
        lifecycle.failed.assert_not_called()

    @pytest.mark.parametrize("ingress_class,ingress_tls,cert_valid,expiration_date,result,success", (
            (Ingress, IngressTLS, True, (datetime.now() + timedelta(days=5)), False, True),
            (V1Ingress, V1IngressTLS, True, (datetime.now() + timedelta(days=5)), False, True),
            (Ingress, IngressTLS, True, None, False, True),
            (V1Ingress, V1IngressTLS, True, None, False, True),
            (Ingress, IngressTLS, True, (datetime.now() - timedelta(days=5)), False, False),
            (V1Ingress, V1IngressTLS, True, (datetime.now() - timedelta(days=5)), False, False),
            (Ingress, IngressTLS, False, None, False, False),
            (V1Ingress, V1IngressTLS, False, None, False, False),
            (Ingress, IngressTLS, False, None, True, True),
            (V1Ingress, V1IngressTLS, False, None, True, True)
    ))
    def test_tls_ingress(self, get, app_spec, bookkeeper, lifecycle, lifecycle_subject, get_cert, ingress_adapter,
                         ingress_class, ingress_tls, cert_valid, expiration_date, result, success, config):
        config.tls_certificate_ready = True
        app_spec = app_spec._replace(ingress_tls=IngressTLSSpec(enabled=True, certificate_issuer=None))
        replicas = 2

        ingress = mock.create_autospec(ingress_class, spec_set=True)
        ingress.spec.tls = [ingress_tls(hosts=["extra1.example.com"], secretName="secret1")]
        ingress_adapter.find.return_value = [ingress]

        get_cert.return_value = self._mock_certificate(cert_valid, expiration_date)
        self._create_response(get, replicas, replicas, replicas, replicas)

        ready = ReadyCheck(app_spec, bookkeeper, lifecycle, lifecycle_subject, ingress_adapter, config)
        if not success:
            ready._fail_after = time_monotonic()

        assert ready() is result
        if result:
            bookkeeper.success.assert_not_called()
            lifecycle.success.assert_not_called()
            bookkeeper.failed.assert_not_called()
            lifecycle.failed.assert_not_called()
        elif success:
            bookkeeper.success.assert_called_with(app_spec)
            lifecycle.success.assert_called_with(lifecycle_subject)
            bookkeeper.failed.assert_not_called()
            lifecycle.failed.assert_not_called()
        else:
            bookkeeper.success.assert_not_called()
            lifecycle.success.assert_not_called()
            bookkeeper.failed.assert_called_with(app_spec)
            lifecycle.failed.assert_called_with(lifecycle_subject)

    def test_deployment_tls_config_no_tls_extension(self, get, app_spec, bookkeeper, lifecycle, lifecycle_subject,
                                                    ingress_adapter, config):
        config.tls_certificate_ready = True
        self._create_response(get)
        ready = ReadyCheck(app_spec, bookkeeper, lifecycle, lifecycle_subject, ingress_adapter, config)

        assert ready() is False
        bookkeeper.success.assert_called_with(app_spec)
        bookkeeper.failed.assert_not_called()
        lifecycle.success.assert_called_with(lifecycle_subject)
        lifecycle.failed.assert_not_called()

    @staticmethod
    def _mock_certificate(desired_status=True, expiration=None):
        cert = mock.create_autospec(Certificate, spec_set=True)
        condition = mock.create_autospec(CertificateCondition)
        condition.type = "Ready"
        condition.status = str(desired_status)
        cert.status.conditions = [condition]

        if expiration:
            cert.status.notAfter = expiration
        else:
            cert.status.notAfter = None

        return cert

    @staticmethod
    def _create_response(get, requested=REPLICAS, replicas=REPLICAS, available=REPLICAS, updated=REPLICAS,
                         generation=0, observed_generation=0):
        get.side_effect = None
        resp = mock.MagicMock()
        get.return_value = resp
        resp.json.return_value = {
            'metadata': pytest.helpers.create_metadata('testapp', generation=generation),
            'spec': {
                'selector': {'matchLabels': {'app': 'testapp'}},
                'template': {
                    'spec': {
                        'containers': [{
                            'name': 'testapp',
                            'image': 'finntech/testimage:version',
                        }]
                    },
                    'metadata': pytest.helpers.create_metadata('testapp')
                },
                'replicas': requested
            },
            'status': {
                'replicas': replicas,
                'availableReplicas': available,
                'unavailableReplicas': replicas - available,
                'updatedReplicas': updated,
                'observedGeneration': observed_generation,
            }
        }

    @staticmethod
    def _create_response_zero_replicas(get):
        get.side_effect = None
        resp = mock.MagicMock()
        get.return_value = resp
        resp.json.return_value = {
            'metadata': pytest.helpers.create_metadata('testapp', generation=0),
            'spec': {
                'selector': {'matchLabels': {'app': 'testapp'}},
                'template': {
                    'spec': {
                        'containers': [{
                            'name': 'testapp',
                            'image': 'finntech/testimage:version',
                        }]
                    },
                    'metadata': pytest.helpers.create_metadata('testapp')
                },
                'replicas': 0
            },
            'status': {
                'observedGeneration': 0,
            }
        }
