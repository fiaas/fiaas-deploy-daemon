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
from fiaas_deploy_daemon.deployer.kubernetes.deployment import StrongboxSecrets, GenericInitSecrets, KubernetesSecrets, \
    Secrets
from fiaas_deploy_daemon.specs.models import StrongboxSpec

CANARY_NAME = "DUMMY"
CANARY_VALUE = "CANARY"
SECRET_IMAGE = "fiaas/secret_image:version"
STRONGBOX_IMAGE = 'fiaas/strongbox_image:version'


def _secrets_mode_ids(fixture_value):
    generic_enabled, strongbox_enabled, app_strongbox_enabled, _ = fixture_value
    return "Generic:{!r:^5}, Strongbox: {!r:^5}, app:{!r:^5}".format(
        generic_enabled, strongbox_enabled, app_strongbox_enabled)


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
        # (Enable generic, Enable strongbox, app strongbox, Name of called mock)
        (True, True, True, "generic_init_secrets"),
        (True, True, False, "generic_init_secrets"),
        (True, False, True, "generic_init_secrets"),
        (True, False, False, "generic_init_secrets"),
        (False, True, True, "strongbox_secrets"),
        (False, True, False, "kubernetes_secrets"),
        (False, False, True, "kubernetes_secrets"),
        (False, False, False, "kubernetes_secrets"),
    ], ids=_secrets_mode_ids)
    def secrets_mode(self, request):
        yield request.param

    @pytest.fixture
    def config(self, secrets_mode):
        generic_enabled, strongbox_enabled, _, _ = secrets_mode
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.secrets_init_container_image = SECRET_IMAGE if generic_enabled else None
        config.secrets_service_account_name = "secretsmanager" if generic_enabled else None
        config.strongbox_init_container_image = STRONGBOX_IMAGE if strongbox_enabled else None
        yield config

    @pytest.fixture
    def kubernetes_secrets(self):
        return mock.create_autospec(KubernetesSecrets(), spec_set=True, instance=True)

    @pytest.fixture
    def generic_init_secrets(self, config):
        return mock.create_autospec(GenericInitSecrets(config), spec_set=True, instance=True)

    @pytest.fixture
    def strongbox_secrets(self, config):
        return mock.create_autospec(StrongboxSecrets(config), spec_set=True, instance=True)

    @pytest.fixture
    def secrets(self, config, kubernetes_secrets, generic_init_secrets, strongbox_secrets):
        return Secrets(config, kubernetes_secrets, generic_init_secrets, strongbox_secrets)

    def test_secret_selection(self, request, secrets_mode, secrets, deployment, app_spec,
                              kubernetes_secrets, generic_init_secrets, strongbox_secrets):
        generic_enabled, strongbox_enabled, app_strongbox_enabled, wanted_mock_name = secrets_mode

        if app_strongbox_enabled:
            strongbox = StrongboxSpec(enabled=True, iam_role="iam_role", aws_region="eu-west-1", groups=["group1"])
        else:
            strongbox = StrongboxSpec(enabled=False, iam_role=None, aws_region="eu-west-1", groups=None)
        app_spec = app_spec._replace(strongbox=strongbox)

        secrets.apply(deployment, app_spec)

        wanted_mock = request.getfixturevalue(wanted_mock_name)
        wanted_mock.apply.assert_called_once_with(deployment, app_spec)
        for m in (kubernetes_secrets, generic_init_secrets, strongbox_secrets):
            if m != wanted_mock:
                m.apply.assert_not_called()


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


class TestGenericInitSecrets(object):
    @pytest.fixture(params=(True, False))
    def use_in_memory_emptydirs(self, request):
        yield request.param

    @pytest.fixture
    def generic_init_secrets(self, use_in_memory_emptydirs):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        config.use_in_memory_emptydirs = use_in_memory_emptydirs
        return GenericInitSecrets(config)

    def test_main_container_volumes(self, deployment, app_spec, generic_init_secrets, use_in_memory_emptydirs):
        generic_init_secrets.apply(deployment, app_spec)

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

    def test_init_container(self, deployment, app_spec, generic_init_secrets):
        generic_init_secrets.apply(deployment, app_spec)

        init_container = deployment.spec.template.spec.initContainers[0]
        assert init_container is not None

        assert "K8S_DEPLOYMENT" == init_container.env[-1].name
        assert app_spec.name == init_container.env[-1].value

    def test_init_container_mounts(self, deployment, app_spec, generic_init_secrets):
        generic_init_secrets.apply(deployment, app_spec)

        mounts = deployment.spec.template.spec.initContainers[0].volumeMounts
        assert mounts[0].name == "{}-secret".format(app_spec.name)
        assert mounts[1].name == "{}-config".format(GenericInitSecrets.SECRETS_INIT_CONTAINER_NAME)
        assert mounts[2].name == "{}-config".format(app_spec.name)
        assert mounts[3].name == "tmp"


class TestStrongboxSecrets(object):
    IAM_ROLE = "arn:aws:iam::12345678:role/the-role-name"
    AWS_REGION = "eu-west-1"
    GROUPS = ["foo", "bar"]

    @pytest.fixture
    def strongbox_secrets(self):
        config = mock.create_autospec(Configuration([]), spec_set=True)
        return StrongboxSecrets(config)

    @pytest.fixture
    def app_spec(self, app_spec):
        strongbox = StrongboxSpec(enabled=True, iam_role=self.IAM_ROLE, aws_region=self.AWS_REGION, groups=self.GROUPS)
        return app_spec._replace(strongbox=strongbox)

    def test_environment(self, deployment, app_spec, strongbox_secrets):
        strongbox_secrets.apply(deployment, app_spec)

        assert 1 == len(deployment.spec.template.spec.initContainers)
        init_container = deployment.spec.template.spec.initContainers[0]
        assert init_container is not None

        assert 3 == len(init_container.env)
        self._assert_env_var(init_container.env[0], "K8S_DEPLOYMENT", app_spec.name)
        self._assert_env_var(init_container.env[1], "AWS_REGION", self.AWS_REGION)
        self._assert_env_var(init_container.env[2], "SECRET_GROUPS", ",".join(self.GROUPS))

    def test_annotations(self, deployment, app_spec, strongbox_secrets):
        strongbox_secrets.apply(deployment, app_spec)

        pod_metadata = deployment.spec.template.metadata
        assert pod_metadata.annotations == {
            CANARY_NAME: CANARY_VALUE,
            "iam.amazonaws.com/role": self.IAM_ROLE
        }

    @staticmethod
    def _assert_env_var(env_var, name, value):
        __tracebackhide__ = True

        assert name == env_var.name
        assert value == env_var.value
