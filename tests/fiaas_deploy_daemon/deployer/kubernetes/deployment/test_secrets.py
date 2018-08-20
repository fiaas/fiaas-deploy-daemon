#!/usr/bin/env python
# -*- coding: utf-8
import mock
import pytest
from k8s.models.deployment import Deployment

from fiaas_deploy_daemon import Configuration
from fiaas_deploy_daemon.deployer.kubernetes.deployment import StrongboxSecrets, GenericInitSecrets, KubernetesSecrets, \
    Secrets
from fiaas_deploy_daemon.specs.models import StrongboxSpec

SECRET_IMAGE = "fiaas/secret_image:version"
STRONGBOX_IMAGE = 'fiaas/strongbox_image:version'


def _secrets_mode_ids(fixture_value):
    generic_enabled, strongbox_enabled, app_strongbox_enabled, _ = fixture_value
    return "Generic:{!r:^5}, Strongbox: {!r:^5}, app:{!r:^5}".format(
        generic_enabled, strongbox_enabled, app_strongbox_enabled)


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

    def test_secret_selection(self, request, secrets_mode, secrets, app_spec, kubernetes_secrets, generic_init_secrets, strongbox_secrets):
        generic_enabled, strongbox_enabled, app_strongbox_enabled, wanted_mock_name = secrets_mode

        if app_strongbox_enabled:
            strongbox = StrongboxSpec(enabled=True, iam_role="iam_role", aws_region="eu-west-1", groups=["group1"])
        else:
            strongbox = StrongboxSpec(enabled=False, iam_role=None, aws_region="eu-west-1", groups=None)
        app_spec = app_spec._replace(strongbox=strongbox)

        deployment = Deployment()
        secrets.apply(deployment, app_spec)

        wanted_mock = request.getfixturevalue(wanted_mock_name)
        wanted_mock.apply.assert_called_once_with(deployment, app_spec)
        for m in (kubernetes_secrets, generic_init_secrets, strongbox_secrets):
            if m != wanted_mock:
                m.apply.assert_not_called()
