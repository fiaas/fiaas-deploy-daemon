
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
import mock
import pytest
from k8s.models.common import ObjectMeta
from k8s.models.resourcequota import ResourceQuota, ResourceQuotaSpec, NotBestEffort, BestEffort

from fiaas_deploy_daemon.config import Configuration
from fiaas_deploy_daemon.deployer.kubernetes.adapter import K8s, _make_selector
from fiaas_deploy_daemon.deployer.kubernetes.autoscaler import AutoscalerDeployer
from fiaas_deploy_daemon.deployer.kubernetes.deployment import DeploymentDeployer
from fiaas_deploy_daemon.deployer.kubernetes.ingress import IngressDeployer
from fiaas_deploy_daemon.deployer.kubernetes.service import ServiceDeployer
from fiaas_deploy_daemon.deployer.kubernetes.service_account import ServiceAccountDeployer
from fiaas_deploy_daemon.specs.models import ResourcesSpec, ResourceRequirementSpec

FIAAS_VERSION = "1"
TEAMS = u"foo"
TAGS = u"bar"


class TestK8s(object):
    @pytest.fixture(autouse=True)
    def service_deployer(self):
        return mock.create_autospec(ServiceDeployer)

    @pytest.fixture(autouse=True)
    def service_account_deployer(self):
        return mock.create_autospec(ServiceAccountDeployer)

    @pytest.fixture(autouse=True)
    def deployment_deployer(self):
        return mock.create_autospec(DeploymentDeployer)

    @pytest.fixture(autouse=True)
    def ingress_deployer(self):
        return mock.create_autospec(IngressDeployer)

    @pytest.fixture(autouse=True)
    def autoscaler_deployer(self):
        return mock.create_autospec(AutoscalerDeployer)

    @pytest.fixture(autouse=True)
    def resource_quota_list(self):
        with mock.patch('k8s.models.resourcequota.ResourceQuota.list') as mockk:
            mockk.return_value = []
            yield mockk

    @pytest.fixture
    def k8s(self, service_deployer, deployment_deployer, ingress_deployer, autoscaler_deployer, service_account_deployer):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.version = FIAAS_VERSION
        return K8s(config, service_deployer, deployment_deployer, ingress_deployer, autoscaler_deployer, service_account_deployer)

    def test_make_labels(self, k8s, app_spec):
        actual = k8s._make_labels(app_spec)
        assert actual["app"] == app_spec.name
        assert actual["fiaas/version"] == app_spec.version
        assert actual["fiaas/deployed_by"] == FIAAS_VERSION
        assert actual["teams.fiaas/{}".format(TEAMS)] == "true"
        assert actual["tags.fiaas/{}".format(TAGS)] == "true"

    def test_make_labels_with_spaces(self, k8s, app_spec_teams_and_tags):
        actual = k8s._make_labels(app_spec_teams_and_tags)
        assert actual["teams.fiaas/order-produkt-betaling"] == "true"
        assert actual["tags.fiaas/hoeyt-i-stacken"] == "true"
        assert actual["tags.fiaas/ad-in"] == "true"
        assert actual["tags.fiaas/anonnseinnlegging"] == "true"

    def test_make_selector(self, app_spec):
        assert _make_selector(app_spec) == {'app': app_spec.name}

    @pytest.mark.parametrize("resource_quota_specs,expect_strip_resources,has_resources", [
        ([], False, True),
        ([], False, False),
        ([{"hard": {"pods": "0"}, "scopes": [NotBestEffort]}], True, True),
        ([{"hard": {"pods": "0"}, "scopes": [NotBestEffort]}], True, False),
        ([{"hard": {"pods": "10"}, "scopes": [NotBestEffort]},
          {"hard": {"pods": "0"}, "scopes": [NotBestEffort]}], True, True),
        ([{"hard": {"pods": "10"}, "scopes": [NotBestEffort]},
          {"hard": {"pods": "0"}, "scopes": [NotBestEffort]}], True, False),
        ([{"hard": {"pods": "10"}, "scopes": [NotBestEffort]}], False, True),
        ([{"hard": {"pods": "10"}, "scopes": [NotBestEffort]}], False, False),
        ([{"hard": {"pods": "0"}, "scopes": [BestEffort]}], False, True),
        ([{"hard": {"pods": "0"}, "scopes": [BestEffort]}], False, False),
    ]
    )
    def test_pass_to_deployment(self, app_spec, k8s, deployment_deployer, resource_quota_list,
                                resource_quota_specs, expect_strip_resources, has_resources):
        explicit_resources = ResourcesSpec(limits=ResourceRequirementSpec(cpu="200m", memory="128M"),
                                           requests=ResourceRequirementSpec(cpu="100m", memory="64M"))
        no_resources = ResourcesSpec(limits=ResourceRequirementSpec(cpu=None, memory=None),
                                     requests=ResourceRequirementSpec(cpu=None, memory=None))

        app_spec = app_spec._replace(resources=explicit_resources if has_resources else no_resources)
        expected_app_spec = app_spec._replace(resources=no_resources) if expect_strip_resources else app_spec

        resource_quotas = [ResourceQuota(metadata=ObjectMeta(name="quota-{}".format(i), namespace=app_spec.namespace),
                                         spec=ResourceQuotaSpec(**spec))
                           for i, spec in enumerate(resource_quota_specs)]
        resource_quota_list.return_value = resource_quotas

        selector = _make_selector(app_spec)
        labels = k8s._make_labels(app_spec)

        k8s.deploy(app_spec)

        pytest.helpers.assert_any_call(deployment_deployer.deploy, expected_app_spec, selector, labels,
                                       expect_strip_resources)

    def test_pass_to_ingress(self, app_spec, k8s, ingress_deployer, resource_quota_list):
        labels = k8s._make_labels(app_spec)

        k8s.deploy(app_spec)

        pytest.helpers.assert_any_call(ingress_deployer.deploy, app_spec, labels)

    def test_pass_to_service(self, app_spec, k8s, service_deployer, resource_quota_list):
        selector = _make_selector(app_spec)
        labels = k8s._make_labels(app_spec)

        k8s.deploy(app_spec)

        pytest.helpers.assert_any_call(service_deployer.deploy, app_spec, selector, labels)

    @pytest.mark.parametrize('service_account_per_app_enabled', (True, False))
    def test_pass_to_service_account(self, app_spec, k8s, service_deployer,
                                     resource_quota_list, deployment_deployer,
                                     ingress_deployer, autoscaler_deployer,
                                     service_account_deployer,
                                     service_account_per_app_enabled):

        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.version = FIAAS_VERSION
        config.enable_service_account_per_app = service_account_per_app_enabled
        k8s = K8s(config, service_deployer, deployment_deployer, ingress_deployer, autoscaler_deployer, service_account_deployer)

        labels = k8s._make_labels(app_spec)

        k8s.deploy(app_spec)

        if service_account_per_app_enabled:
            pytest.helpers.assert_any_call(service_account_deployer.deploy, app_spec, labels)
        else:
            service_account_deployer.deploy.assert_not_called()
