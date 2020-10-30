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
import mock
import pytest
from k8s.models.common import ObjectMeta
from k8s.models.deployment import Deployment, DeploymentSpec
from k8s.models.pod import Container, PodSpec, PodTemplateSpec, EnvVar

from fiaas_deploy_daemon import Configuration
from fiaas_deploy_daemon.deployer.kubernetes.deployment import GenericInitSecrets, KubernetesSecrets, \
    Secrets
from fiaas_deploy_daemon.specs.models import StrongboxSpec, SecretsSpec

CANARY_NAME = "DUMMY"
CANARY_VALUE = "CANARY"
SECRET_IMAGE = "fiaas/secret_image:version"
STRONGBOX_IMAGE = 'fiaas/strongbox_image:version'
DEFAULT_IMAGE = "some/image:version"

APP_SPEC_SECRETS = [SecretsSpec(type='some-provider', parameters={}, annotations={})]


def _secrets_mode_ids(fixture_value):
    generic_enabled, strongbox_enabled, app_strongbox_enabled, app_spec_secrets_enabled, default_enabled, _ = fixture_value
    return "Generic:{!r:^5}, Strongbox: {!r:^5}, app_strongbox:{!r:^5}, app_spec_secrets:{!r:^5}, default:{!r:^5}".format(
        generic_enabled, strongbox_enabled, app_strongbox_enabled, app_spec_secrets_enabled, default_enabled)


@pytest.fixture
def deployment():
    main_container = Container(env=[EnvVar(name=CANARY_NAME, value=CANARY_VALUE)])
    pod_spec = PodSpec(containers=[main_container])
    pod_metadata = ObjectMeta(annotations={CANARY_NAME: CANARY_VALUE})
    pod_template_spec = PodTemplateSpec(spec=pod_spec, metadata=pod_metadata)
    deployment_spec = DeploymentSpec(template=pod_template_spec)
    return Deployment(spec=deployment_spec)


class TestSecrets(object):
    @pytest.fixture(params=[
        # (Enable generic, Enable strongbox, app strongbox, app-spec secrets, default_secret Name of called mock)
        (True, True, True, False, False, "generic_init_secrets"),
        (True, True, True, False, True, "generic_init_secrets"),
        (True, True, True, True, False, "generic_init_secrets"),
        (True, True, True, True, True, "generic_init_secrets"),
        (True, True, False, False, False, "generic_init_secrets"),
        (True, True, False, False, True, "generic_init_secrets"),
        (True, True, False, True, False, "generic_init_secrets"),
        (True, True, False, True, True, "generic_init_secrets"),
        (True, False, True, False, False, "generic_init_secrets"),
        (True, False, True, False, True, "generic_init_secrets"),
        (True, False, True, True, False, "generic_init_secrets"),
        (True, False, True, True, True, "generic_init_secrets"),
        (True, False, False, False, False, "generic_init_secrets"),
        (True, False, False, False, True, "generic_init_secrets"),
        (True, False, False, True, False, "generic_init_secrets"),
        (True, False, False, True, True, "generic_init_secrets"),
        (False, True, True, False, False, "generic_init_secrets"),
        (False, True, True, False, True, "generic_init_secrets"),
        (False, True, True, True, False, "generic_init_secrets"),
        (False, True, True, True, True, "generic_init_secrets"),
        (False, True, False, False, False, "kubernetes_secrets"),
        (False, True, False, False, True, "generic_init_secrets"),
        (False, True, False, True, False, "generic_init_secrets"),
        (False, True, False, True, True, "generic_init_secrets"),
        (False, False, True, False, False, "kubernetes_secrets"),
        (False, False, True, False, True, "generic_init_secrets"),
        (False, False, True, True, False, "generic_init_secrets"),
        (False, False, True, True, True, "generic_init_secrets"),
        (False, False, False, False, False, "kubernetes_secrets"),
        (False, False, False, False, True, "generic_init_secrets"),
        (False, False, False, True, False, "generic_init_secrets"),
        (False, False, False, True, True, "generic_init_secrets"),
    ], ids=_secrets_mode_ids)
    def secrets_mode(self, request):
        yield request.param

    @pytest.fixture
    def config(self, secrets_mode):
        generic_enabled, strongbox_enabled, _, _, default_enabled, _ = secrets_mode
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.secrets_init_container_image = SECRET_IMAGE if generic_enabled else None
        config.secrets_service_account_name = "secretsmanager" if generic_enabled else None
        config.strongbox_init_container_image = STRONGBOX_IMAGE if strongbox_enabled else None
        config.secret_init_containers = {"default": DEFAULT_IMAGE} if default_enabled else {}
        yield config

    @pytest.fixture
    def kubernetes_secrets(self):
        return mock.create_autospec(KubernetesSecrets(), spec_set=True, instance=True)

    @pytest.fixture
    def generic_init_secrets(self, config):
        return mock.create_autospec(GenericInitSecrets(config), spec_set=True, instance=True)

    @pytest.fixture
    def secrets(self, config, kubernetes_secrets, generic_init_secrets):
        return Secrets(config, kubernetes_secrets, generic_init_secrets)

    @staticmethod
    def mock_supports(generic_enabled, strongbox_enabled, default_enabled):
        def wrapped(_type):
            if _type == "strongbox" and strongbox_enabled:
                return True
            if _type == "default" and (generic_enabled or default_enabled):
                return True
            return False

        return wrapped

    def test_secret_selection(self, request, secrets_mode, secrets, deployment, app_spec,
                              kubernetes_secrets, generic_init_secrets, config):
        generic_enabled, strongbox_enabled, app_strongbox_enabled, app_spec_secrets_enabled, default_enabled, \
            wanted_mock_name = secrets_mode

        generic_init_secrets.supports.side_effect = self.mock_supports(generic_enabled, strongbox_enabled, default_enabled)

        if not generic_enabled:
            assert config.secrets_init_container_image is None

        if app_strongbox_enabled:
            strongbox = StrongboxSpec(enabled=True, iam_role="iam_role", aws_region="eu-west-1", groups=["group1", "group2"])
        else:
            strongbox = StrongboxSpec(enabled=False, iam_role=None, aws_region="eu-west-1", groups=None)

        if app_spec_secrets_enabled:
            app_spec_secrets = APP_SPEC_SECRETS
        else:
            app_spec_secrets = []

        app_spec = app_spec._replace(strongbox=strongbox, secrets=app_spec_secrets)

        secrets.apply(deployment, app_spec)

        wanted_mock = request.getfixturevalue(wanted_mock_name)

        if wanted_mock == generic_init_secrets:
            kubernetes_secrets.apply.assert_not_called()
            generic_init_secrets.apply.assert_called_once()
        else:
            generic_init_secrets.apply.assert_not_called()
            kubernetes_secrets.apply.assert_called_once()

    def test_generic_secrets(self, deployment, app_spec):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.secrets_init_container_image = SECRET_IMAGE
        config.secrets_service_account_name = "secretsmanager"

        generic_init_secrets = mock.create_autospec(GenericInitSecrets(config), spec_set=True, instance=True)
        generic_init_secrets.supports.side_effect = lambda _type: _type == 'default'

        secrets = Secrets(config, mock.create_autospec(KubernetesSecrets(), spec_set=True, instance=True), generic_init_secrets)

        expected_spec = SecretsSpec(type="default",
                                    parameters={},
                                    annotations={})

        secrets.apply(deployment, app_spec)

        generic_init_secrets.apply.assert_called_once_with(deployment, app_spec, expected_spec)

    def test_legacy_strongbox_secrets(self, deployment, app_spec):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.strongbox_init_container_image = STRONGBOX_IMAGE

        app_spec = app_spec._replace(
            strongbox=StrongboxSpec(enabled=True, iam_role="iam_role", aws_region="eu-west-1", groups=["group1", "group2"]))

        generic_init_secrets = mock.create_autospec(GenericInitSecrets(config), spec_set=True, instance=True)
        generic_init_secrets.supports.side_effect = lambda _type: _type == 'strongbox'

        secrets = Secrets(config, mock.create_autospec(KubernetesSecrets(), spec_set=True, instance=True), generic_init_secrets)

        expected_spec = SecretsSpec(type="strongbox",
                                    parameters={"AWS_REGION": "eu-west-1", "SECRET_GROUPS": "group1,group2"},
                                    annotations={"iam.amazonaws.com/role": "iam_role"})

        secrets.apply(deployment, app_spec)

        generic_init_secrets.apply.assert_called_once_with(deployment, app_spec, expected_spec)

    def test_app_spec_secrets(self, deployment, app_spec):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        app_spec = app_spec._replace(secrets=APP_SPEC_SECRETS)
        generic_init_secrets = mock.create_autospec(GenericInitSecrets(config), spec_set=True, instance=True)
        secrets = Secrets(config, mock.create_autospec(KubernetesSecrets(), spec_set=True, instance=True), generic_init_secrets)
        expected_spec = APP_SPEC_SECRETS[0]

        secrets.apply(deployment, app_spec)

        generic_init_secrets.apply.assert_called_once_with(deployment, app_spec, expected_spec)

    def test_default_secrets(self, deployment, app_spec):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.secret_init_containers = {"default": DEFAULT_IMAGE}

        generic_init_secrets = mock.create_autospec(GenericInitSecrets(config), spec_set=True, instance=True)
        generic_init_secrets.supports.side_effect = lambda _type: _type == 'default'

        secrets = Secrets(config, mock.create_autospec(KubernetesSecrets(), spec_set=True, instance=True), generic_init_secrets)

        expected_spec = SecretsSpec(type="default",
                                    parameters={},
                                    annotations={})

        secrets.apply(deployment, app_spec)

        generic_init_secrets.apply.assert_called_once_with(deployment, app_spec, expected_spec)


class TestKubernetesSecrets(object):
    def test_volumes(self, deployment, app_spec):
        kubernetes_secret = KubernetesSecrets()
        kubernetes_secret.apply(deployment, app_spec)

        secret_volume = deployment.spec.template.spec.volumes[-1]
        assert secret_volume.secret.secretName == app_spec.name

        secret_mount = deployment.spec.template.spec.containers[0].volumeMounts[-1]
        assert secret_mount.name == secret_volume.name
        assert secret_mount.mountPath == "/var/run/secrets/fiaas/"
        assert secret_mount.readOnly is True

    def test_secrets_in_environments(self, deployment, app_spec):
        app_spec = app_spec._replace(secrets_in_environment=True)
        ks = KubernetesSecrets()
        ks.apply(deployment, app_spec)

        secret_env_from = deployment.spec.template.spec.containers[0].envFrom[-1]
        assert secret_env_from.secretRef.name == app_spec.name


class TestRegisteredInitSecrets(object):
    @pytest.fixture
    def generic_init_secrets(self):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.secret_init_containers = {
            "default": "default-image",
            "some-provider": "some-secret-container-image"
        }
        return GenericInitSecrets(config)

    @pytest.fixture
    def secrets_spec(self):
        return SecretsSpec(type="some-provider",
                           parameters={},
                           annotations={})

    def test_init_container(self, deployment, app_spec, generic_init_secrets, secrets_spec):
        generic_init_secrets.apply(deployment, app_spec, secrets_spec)

        init_container = deployment.spec.template.spec.initContainers[0]
        assert init_container is not None
        assert init_container.image == "some-secret-container-image"

    def test_not_registered(self, deployment, app_spec, generic_init_secrets, secrets_spec):
        secrets_spec = secrets_spec._replace(type="other-type")
        generic_init_secrets.apply(deployment, app_spec, secrets_spec)

        assert len(deployment.spec.template.spec.initContainers) == 0


class TestDefaultGenericInitSecrets(object):
    @pytest.fixture(params=(True, False))
    def use_in_memory_emptydirs(self, request):
        yield request.param

    @pytest.fixture
    def generic_init_secrets(self, use_in_memory_emptydirs):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.secret_init_containers = {}
        config.use_in_memory_emptydirs = use_in_memory_emptydirs
        config.secrets_init_container_image = "some-image"
        return GenericInitSecrets(config)

    @pytest.fixture
    def secrets_spec(self):
        return SecretsSpec(type="default",
                           parameters={},
                           annotations={})

    def test_main_container_volumes(self, deployment, app_spec, generic_init_secrets, use_in_memory_emptydirs, secrets_spec):
        assert generic_init_secrets.supports("default")
        generic_init_secrets.apply(deployment, app_spec, secrets_spec)

        secret_volume = deployment.spec.template.spec.volumes[0]
        assert secret_volume.emptyDir is not None
        emptydir_medium = "Memory" if use_in_memory_emptydirs else None
        assert secret_volume.emptyDir.medium == emptydir_medium
        assert secret_volume.name == "{}-secret".format(app_spec.name)
        config_volume = deployment.spec.template.spec.volumes[1]
        assert config_volume.name == "{}-config".format(GenericInitSecrets.SECRETS_INIT_CONTAINER_NAME)

        secret_mount = deployment.spec.template.spec.containers[0].volumeMounts[-1]
        assert secret_mount.name == secret_volume.name
        assert secret_mount.mountPath == "/var/run/secrets/fiaas/"
        assert secret_mount.readOnly is True

    def test_init_container(self, deployment, app_spec, generic_init_secrets, secrets_spec):
        generic_init_secrets.apply(deployment, app_spec, secrets_spec)

        init_container = deployment.spec.template.spec.initContainers[0]
        assert init_container is not None

        assert "K8S_DEPLOYMENT" == init_container.env[-1].name
        assert app_spec.name == init_container.env[-1].value

    def test_init_container_mounts(self, deployment, app_spec, generic_init_secrets, secrets_spec):
        generic_init_secrets.apply(deployment, app_spec, secrets_spec)

        mounts = deployment.spec.template.spec.initContainers[0].volumeMounts
        assert mounts[0].name == "{}-secret".format(app_spec.name)
        assert mounts[1].name == "{}-config".format(GenericInitSecrets.SECRETS_INIT_CONTAINER_NAME)
        assert mounts[2].name == "{}-config".format(app_spec.name)
        assert mounts[3].name == "tmp"


class TestStrongboxSecrets(object):
    IAM_ROLE = "arn:aws:iam::12345678:role/the-role-name"
    AWS_REGION = "eu-west-1"
    GROUPS = "foo,bar"

    @pytest.fixture
    def strongbox_secrets(self):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.secret_init_containers = {}
        config.strongbox_init_container_image = "some-strongbox-image"
        return GenericInitSecrets(config)

    @pytest.fixture
    def secrets_spec(self, app_spec):
        return SecretsSpec(type="strongbox",
                           parameters={"AWS_REGION": self.AWS_REGION, "SECRET_GROUPS": self.GROUPS},
                           annotations={"iam.amazonaws.com/role": self.IAM_ROLE})

    def test_environment(self, deployment, app_spec, strongbox_secrets, secrets_spec):
        assert strongbox_secrets.supports("strongbox")
        strongbox_secrets.apply(deployment, app_spec, secrets_spec)

        assert 1 == len(deployment.spec.template.spec.initContainers)
        init_container = deployment.spec.template.spec.initContainers[0]
        assert init_container is not None

        expected = [
            EnvVar(name="AWS_REGION", value=self.AWS_REGION),
            EnvVar(name="SECRET_GROUPS", value=self.GROUPS),
            EnvVar(name="K8S_DEPLOYMENT", value=app_spec.name),
        ]
        assert init_container.env == expected

    def test_annotations(self, deployment, app_spec, strongbox_secrets, secrets_spec):
        strongbox_secrets.apply(deployment, app_spec, secrets_spec)

        pod_metadata = deployment.spec.template.metadata
        assert pod_metadata.annotations == {
            CANARY_NAME: CANARY_VALUE,
            "iam.amazonaws.com/role": self.IAM_ROLE
        }
