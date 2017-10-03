import mock
import pytest

from k8s.models.resourcequota import ResourceQuota, ResourceQuotaSpec, NotBestEffort, BestEffort
from k8s.models.common import ObjectMeta

from fiaas_deploy_daemon.deployer.kubernetes.adapter import K8s, _make_selector
from fiaas_deploy_daemon.deployer.kubernetes.service import ServiceDeployer
from fiaas_deploy_daemon.deployer.kubernetes.deployment import DeploymentDeployer
from fiaas_deploy_daemon.deployer.kubernetes.ingress import IngressDeployer
from fiaas_deploy_daemon.deployer.kubernetes.autoscaler import AutoscalerDeployer
from fiaas_deploy_daemon.config import Configuration
from fiaas_deploy_daemon.specs.models import ResourcesSpec, ResourceRequirementSpec

FIAAS_VERSION = "1"
TEAMS = u"foo"
TAGS = u"bar"


class TestK8s(object):
    @pytest.fixture(autouse=True)
    def service_deployer(self):
        return mock.create_autospec(ServiceDeployer)

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
    def k8s(self, service_deployer, deployment_deployer, ingress_deployer, autoscaler_deployer):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.version = FIAAS_VERSION
        return K8s(config, service_deployer, deployment_deployer, ingress_deployer, autoscaler_deployer)

    def test_make_labels(self, k8s, app_spec):
        actual = k8s._make_labels(app_spec)
        assert actual["app"] == app_spec.name
        assert actual["fiaas/version"] == app_spec.version
        assert actual["fiaas/deployed_by"] == FIAAS_VERSION
        assert actual["fiaas/teams"] == TEAMS
        assert actual["fiaas/tags"] == TAGS

    def test_make_labels_with_spaces(self, k8s, app_spec_teams_and_tags):
        actual = k8s._make_labels(app_spec_teams_and_tags)
        assert actual["fiaas/teams"] == "order-produkt-betaling"
        assert actual["fiaas/tags"] == "hoeyt-i-stacken"
        assert actual["fiaas/tags_1"] == "ad-in"
        assert actual["fiaas/tags_2"] == "anonnseinnlegging"

    def test_make_selector(self, app_spec):
        assert _make_selector(app_spec) == {'app': app_spec.name}

    def test_pass_to_deployment(self, app_spec, k8s, deployment_deployer, resource_quota_list):
        selector = _make_selector(app_spec)
        labels = k8s._make_labels(app_spec)

        k8s.deploy(app_spec)

        pytest.helpers.assert_any_call(deployment_deployer.deploy, app_spec, selector, labels)

    def test_pass_to_ingress(self, app_spec, k8s, ingress_deployer, resource_quota_list):
        labels = k8s._make_labels(app_spec)

        k8s.deploy(app_spec)

        pytest.helpers.assert_any_call(ingress_deployer.deploy, app_spec, labels)

    def test_pass_to_service(self, app_spec, k8s, service_deployer, resource_quota_list):
        selector = _make_selector(app_spec)
        labels = k8s._make_labels(app_spec)

        k8s.deploy(app_spec)

        pytest.helpers.assert_any_call(service_deployer.deploy, app_spec, selector, labels)

    def test_pass_to_deployment_with_stripped_resources_when_resourcequota_denies(self, app_spec, k8s,
                                                                                  deployment_deployer,
                                                                                  resource_quota_list):
        selector = _make_selector(app_spec)
        labels = k8s._make_labels(app_spec)

        not_besteffort = ResourceQuota(
            metadata=ObjectMeta(name="not-besteffort", namespace=app_spec.namespace),
            spec=ResourceQuotaSpec(hard={"pods": "0"}, scopes=[NotBestEffort])
        )
        resource_quota_list.return_value = [not_besteffort]

        no_requirements = ResourceRequirementSpec(cpu=None, memory=None)
        app_spec_resources_stripped = app_spec._replace(
            resources=ResourcesSpec(limits=no_requirements, requests=no_requirements))

        k8s.deploy(app_spec)

        pytest.helpers.assert_any_call(deployment_deployer.deploy, app_spec_resources_stripped, selector, labels)

    def test_pass_to_deployment_with_resources_when_no_resourcequota(self, app_spec, k8s, deployment_deployer,
                                                                     resource_quota_list):

        app_spec = app_spec._replace(
            resources=ResourcesSpec(
                limits=ResourceRequirementSpec(cpu="200m", memory="128M"),
                requests=ResourceRequirementSpec(cpu="100m", memory="64M")
            )
        )

        selector = _make_selector(app_spec)
        labels = k8s._make_labels(app_spec)

        k8s.deploy(app_spec)

        pytest.helpers.assert_any_call(deployment_deployer.deploy, app_spec, selector, labels)

    def test_pass_to_deployment_with_resources_when_resourcequota_allows_n(self, app_spec, k8s, deployment_deployer,
                                                                           resource_quota_list):

        app_spec = app_spec._replace(
            resources=ResourcesSpec(
                limits=ResourceRequirementSpec(cpu="200m", memory="128M"),
                requests=ResourceRequirementSpec(cpu="100m", memory="64M")
            )
        )

        selector = _make_selector(app_spec)
        labels = k8s._make_labels(app_spec)

        not_besteffort = ResourceQuota(
            metadata=ObjectMeta(name="not-besteffort", namespace=app_spec.namespace),
            spec=ResourceQuotaSpec(hard={"pods": "100"}, scopes=[NotBestEffort])
        )
        resource_quota_list.return_value = [not_besteffort]

        resource_quota_list.return_value = []

        k8s.deploy(app_spec)

        pytest.helpers.assert_any_call(deployment_deployer.deploy, app_spec, selector, labels)

    def test_pass_to_deployment_with_resources_when_resourcequota_allows_besteffort(self, app_spec, k8s,
                                                                                    deployment_deployer,
                                                                                    resource_quota_list):

        app_spec = app_spec._replace(
            resources=ResourcesSpec(
                limits=ResourceRequirementSpec(cpu="200m", memory="128M"),
                requests=ResourceRequirementSpec(cpu="100m", memory="64M")
            )
        )

        selector = _make_selector(app_spec)
        labels = k8s._make_labels(app_spec)

        not_besteffort = ResourceQuota(
            metadata=ObjectMeta(name="besteffort", namespace=app_spec.namespace),
            spec=ResourceQuotaSpec(hard={"pods": "0"}, scopes=[BestEffort])
        )
        resource_quota_list.return_value = [not_besteffort]

        resource_quota_list.return_value = []

        k8s.deploy(app_spec)

        pytest.helpers.assert_any_call(deployment_deployer.deploy, app_spec, selector, labels)
