#!/usr/bin/env python
# -*- coding: utf-8

import pytest

from fiaas_deploy_daemon.config import Configuration


class TestConfig(object):
    def test_resolve_finn_env(self, monkeypatch):
        environment = "Some environment"
        monkeypatch.setenv("FINN_ENV", environment)
        config = Configuration([])

        assert config.target_cluster == environment

    @pytest.mark.parametrize("format", ["plain", "json"])
    def test_resolve_log_format_env(self, monkeypatch, format):
        monkeypatch.setenv("LOG_FORMAT", format)
        config = Configuration([])

        assert config.log_format == format

    def test_invalid_log_format_env(self, monkeypatch):
        monkeypatch.setenv("LOG_FORMAT", "fail")

        with pytest.raises(SystemExit):
            Configuration([])

    @pytest.mark.parametrize("format", ["plain", "json"])
    def test_log_format_param(self, format):
        config = Configuration(["--log-format", format])

        assert config.log_format == format

    def test_invalid_log_format_param(self):
        with pytest.raises(SystemExit):
            Configuration(["--log-format", "fail"])

    def test_default_parameter_values(self):
        config = Configuration([])

        assert not config.debug
        assert config.api_server == 'https://kubernetes.default.svc.cluster.local'
        assert config.api_token is None
        assert config.target_cluster is None
        assert config.log_format == "plain"
        assert config.image == ""

    @pytest.mark.parametrize("arg,key", [
        ("--api-server", "api_server"),
        ("--api-token", "api_token"),
        ("--api-cert", "api_cert"),
        ("--target-cluster", "target_cluster"),
        ("--proxy", "proxy")
    ])
    def test_parameters(self, arg, key):
        config = Configuration([arg, "value"])

        assert getattr(config, key) == "value"

    @pytest.mark.parametrize("env,key", [
        ("API_SERVER", "api_server"),
        ("API_TOKEN", "api_token"),
        ("API_CERT", "api_cert"),
        ("FINN_ENV", "target_cluster"),
        ("IMAGE", "image")
    ])
    def test_env(self, monkeypatch, env, key):
        monkeypatch.setenv(env, "value")
        config = Configuration([])

        assert getattr(config, key) == "value"

    def test_debug(self):
        config = Configuration(["--debug"])

        assert config.debug

    @pytest.mark.parametrize("service", ["kafka_pipeline"])
    def test_resolve_service(self, monkeypatch, service):
        monkeypatch.setenv(service.upper() + "_SERVICE_HOST", "host")
        monkeypatch.setenv(service.upper() + "_SERVICE_PORT", "1234")
        config = Configuration([])

        host, port = config.resolve_service(service)
        assert host == "host"
        assert port == 1234

    @pytest.mark.parametrize("service_exists", [True, False])
    def test_has_service(self, monkeypatch, service_exists):
        service = "service"
        if service_exists:
            monkeypatch.setenv(service.upper() + "_SERVICE_HOST", "host")
            monkeypatch.setenv(service.upper() + "_SERVICE_PORT", "1234")
        config = Configuration([])

        assert service_exists == config.has_service(service)

    def test_new_secret_key_every_time(self):
        cfg1 = Configuration([])
        cfg2 = Configuration([])

        assert cfg1.SECRET_KEY != cfg2.SECRET_KEY

    @pytest.mark.parametrize("cmdline,envvar,expected", [
        ([], "", "http://puppetproxy.finntech.no:42042"),
        ([], "http://proxy.example.com", "http://proxy.example.com"),
        (["--no-proxy"], "", ""),
        (["--no-proxy"], "http://proxy.example.com", "")
    ])
    def test_proxy(self, monkeypatch, cmdline, envvar, expected):
        if envvar:
            monkeypatch.setenv("HTTP_PROXY", envvar)
        config = Configuration(cmdline)

        assert config.proxy == expected
