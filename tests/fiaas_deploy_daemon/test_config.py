#!/usr/bin/env python
# -*- coding: utf-8

import pytest
import dns.rdata
from fiaas_deploy_daemon.config import Configuration
from dns import resolver as resolver


class TestConfig(object):
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
        assert config.environment == ""
        assert config.infrastructure == "diy"
        assert config.log_format == "plain"
        assert config.image == ""

    @pytest.mark.parametrize("arg,key", [
        ("--api-server", "api_server"),
        ("--api-token", "api_token"),
        ("--api-cert", "api_cert"),
        ("--environment", "environment"),
        ("--proxy", "proxy")
    ])
    def test_parameters(self, arg, key):
        config = Configuration([arg, "value"])

        assert getattr(config, key) == "value"

    def test_infrastructure_param(self):
        config = Configuration(["--infrastructure", "gke"])

        assert config.infrastructure == "gke"

    @pytest.mark.parametrize("env,key", [
        ("API_SERVER", "api_server"),
        ("API_TOKEN", "api_token"),
        ("API_CERT", "api_cert"),
        ("FIAAS_ENVIRONMENT", "environment"),
        ("IMAGE", "image")
    ])
    def test_env(self, monkeypatch, env, key):
        monkeypatch.setenv(env, "value")
        config = Configuration([])

        assert getattr(config, key) == "value"

    def test_infrastructure_env(self, monkeypatch):
        monkeypatch.setenv("FIAAS_INFRASTRUCTURE", "gke")
        config = Configuration([])

        assert config.infrastructure == "gke"

    def test_debug(self):
        config = Configuration(["--debug"])

        assert config.debug

    def test_resolve_service_from_dns(self, monkeypatch):
        monkeypatch.setattr(resolver, "query", lambda x, y: dns.rdataset.from_text(
            'IN',
            'SRV',
            3600,
            '10 100 7794 kafka-pipeline.default.svc.cluster.local.'))

        config = Configuration([])

        target, port = config.resolve_service('service', 'port')
        assert target == 'kafka-pipeline.default.svc.cluster.local'
        assert port == 7794

    @pytest.mark.parametrize("service", ["kafka_pipeline"])
    def test_resolve_service_from_env(self, monkeypatch, service):

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
        ([], "", None),
        (["--infrastructure", "gke"], "", None),
        ([], "http://proxy.example.com", "http://proxy.example.com"),
        (["--infrastructure", "gke"], "http://proxy.example.com", "http://proxy.example.com"),
        (["--proxy", "http://proxy.example.com"], "", "http://proxy.example.com"),
    ])
    def test_proxy(self, monkeypatch, cmdline, envvar, expected):
        if envvar:
            monkeypatch.setenv("http_proxy", envvar)
        config = Configuration(cmdline)

        assert config.proxy == expected
