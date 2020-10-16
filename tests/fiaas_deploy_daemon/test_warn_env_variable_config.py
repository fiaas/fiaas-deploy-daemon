from fiaas_deploy_daemon.config import Configuration, HostRewriteRule
from fiaas_deploy_daemon import warn_if_env_variable_config

import logging

import mock
import pytest


class ConfigFlag():
    def __init__(self, env_key, env_value, config_key=None, config_value=None):
        self.env_key = env_key
        self.env_value = env_value
        self.config_key = config_key if config_key is not None else env_key.lower()
        self.config_value = config_value if config_value is not None else env_value


@pytest.fixture()
def config_flags():
    yield [
        ConfigFlag('SECRETS_DIRECTORY', '/path/to/test'),
        ConfigFlag('LOG_FORMAT', 'json'),
        ConfigFlag('http_proxy', 'http://localhost:1234', config_key='proxy'),
        ConfigFlag('DEBUG', 'true', config_value=True),
        ConfigFlag('FIAAS_ENVIRONMENT', 'dev', config_key='environment'),
        ConfigFlag('FIAAS_SERVICE_TYPE', 'NodePort', config_key='service_type'),
        ConfigFlag('FIAAS_INFRASTRUCTURE', 'gke', config_key='infrastructure'),
        ConfigFlag('PORT', '9999', config_value=9999),
        ConfigFlag('ENABLE_CRD_SUPPORT', 'true', config_value=True),
        ConfigFlag('SECRETS_INIT_CONTAINER_IMAGE', 'fiaas/fictional_secrets_init_container_image:latest'),
        ConfigFlag('SECRETS_SERVICE_ACCOUNT_NAME', 'secrets_service_account_name'),
        ConfigFlag('DATADOG_CONTAINER_IMAGE', 'fiaas/fictional_datadog_container_image:latest'),
        ConfigFlag('DATADOG_CONTAINER_MEMORY', '100M'),
        ConfigFlag('FIAAS_DATADOG_GLOBAL_TAGS', '[pattern=value,FIAAS_DD_tag=test]', config_key='datadog_global_tags',
                   config_value={'pattern': 'value', 'FIAAS_DD_tag': 'test'}),
        ConfigFlag('PRE_STOP_DELAY', '2', config_value=2),
        ConfigFlag('STRONGBOX_INIT_CONTAINER_IMAGE', 'fiaas/fictional_strongbox_init_container_image'),
        ConfigFlag('ENABLE_DEPRECATED_MULTI_NAMESPACE_SUPPORT', 'true', config_value=True),
        ConfigFlag('USE_INGRESS_TLS', 'default_off'),
        ConfigFlag('TLS_CERTIFICATE_ISSUER', 'a_certificate_issuer'),
        ConfigFlag('USE_IN_MEMORY_EMPTYDIRS', 'true', config_value=True),
        ConfigFlag('DEPLOYMENT_MAX_SURGE', '50%'),
        ConfigFlag('DEPLOYMENT_MAX_UNAVAILABLE', '50%'),
        ConfigFlag('READY_CHECK_TIMEOUT_MULTIPLIER', '7', config_value=7),
        ConfigFlag('DISABLE_DEPRECATED_MANAGED_ENV_VARS', 'true', config_value=True),
        ConfigFlag('USAGE_REPORTING_CLUSTER_NAME', 'cluster_name'),
        ConfigFlag('USAGE_REPORTING_OPERATOR', 'usage_operator'),
        ConfigFlag('USAGE_REPORTING_ENDPOINT', 'http://localhost'),
        ConfigFlag('USAGE_REPORTING_TENANT', 'usage_tenant'),
        ConfigFlag('USAGE_REPORTING_TEAM', 'usage_team'),
        ConfigFlag('API_SERVER', 'http://localhost'),
        ConfigFlag('API_TOKEN', 'api_token'),
        ConfigFlag('API_CERT', 'api_cert'),
        ConfigFlag('CLIENT_CERT', 'client_cert'),
        ConfigFlag('CLIENT_KEY', 'client_key'),
        ConfigFlag('INGRESS_SUFFIXES', r'[1\.example.com,2.example.com]', config_value=[r'1\.example.com', '2.example.com']),
        ConfigFlag('HOST_REWRITE_RULES', r'[pattern=value,(\d+)\.example\.com=$1.example.net,www.([a-z]+.com)={env}.$1]',
                   config_value=[HostRewriteRule('pattern=value'),
                                 HostRewriteRule(r'(\d+)\.example\.com=$1.example.net'),
                                 HostRewriteRule('www.([a-z]+.com)={env}.$1')]),
        ConfigFlag('FIAAS_GLOBAL_ENV', '[pattern=value,FIAAS_ENV=test]', config_key='global_env',
                   config_value={'pattern': 'value', 'FIAAS_ENV': 'test'}),
        ConfigFlag('FIAAS_SECRET_INIT_CONTAINERS',
                   '[default=fiaas/fictional_secrets_init_container_image:latest,other=fiaas/other_secrets_init_container_image:latest]',
                   config_key='secret_init_containers',
                   config_value={'default': 'fiaas/fictional_secrets_init_container_image:latest',
                                 'other': 'fiaas/other_secrets_init_container_image:latest'}),
    ]


def test_warn_if_env_variable_config(monkeypatch, config_flags):
    for config_flag in config_flags:
        monkeypatch.setenv(config_flag.env_key, config_flag.env_value)

    config = Configuration([])

    log = mock.MagicMock(spec=logging.Logger)
    warn_if_env_variable_config(config, log)

    expected_env_keys = ', '.join(sorted(cf.env_key for cf in config_flags))
    expected_log_message = (
        "found configuration environment variables %s. The ability to configure fiaas-deploy-daemon via environment variables has been "
        "removed. If you are trying to use these environment variables to configure fiaas-deploy-daemon, that configuration will not take "
        "effect. Please switch to configuring via a config file/ConfigMap or command-line flags. See "
        "https://github.com/fiaas/fiaas-deploy-daemon/issues/12 for more information."
    )
    log.warn.assert_called_once_with(expected_log_message, expected_env_keys)


def test_dont_warn_if_no_env_config():
    config = Configuration([])

    log = mock.MagicMock(spec=logging.Logger)
    warn_if_env_variable_config(config, log)

    log.warn.assert_not_called()
