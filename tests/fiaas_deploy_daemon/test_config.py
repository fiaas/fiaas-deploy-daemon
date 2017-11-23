#!/usr/bin/env python
# -*- coding: utf-8

import dns.rdata
import mock
import pyaml
import pytest

from fiaas_deploy_daemon.config import Configuration, HostRewriteRule, KeyValue


class TestConfig(object):
    @pytest.fixture(autouse=True)
    def dns_resolver(self):
        with mock.patch("dns.resolver.query") as mock_resolver:
            mock_resolver.side_effect = dns.resolver.NXDOMAIN
            yield mock_resolver

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
        assert config.blacklist == []
        assert config.whitelist == []

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

    @pytest.mark.parametrize("key", ("debug", "enable_tpr_support", "enable_crd_support"))
    def test_flags(self, key):
        flag = "--{}".format(key.replace("_", "-"))
        config = Configuration([])
        assert getattr(config, key) is False
        config = Configuration([flag])
        assert getattr(config, key) is True

    def test_resolve_service_from_dns(self, dns_resolver):
        dns_resolver.side_effect = None
        dns_resolver.return_value = dns.rdataset.from_text('IN', 'SRV', 3600,
                                                           '10 100 7794 kafka-pipeline.default.svc.cluster.local.')

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

    @pytest.mark.parametrize("key,attr,value", [
        ("environment", "environment", "gke"),
        ("proxy", "proxy", "http://proxy.example.com"),
        ("ingress-suffix", "ingress_suffixes", ["1\.example.com", "2.example.com"]),
        ("blacklist", "blacklist", ["app1", "app2"]),
        ("whitelist", "whitelist", ["app1", "app2"]),
    ])
    def test_config_from_file(self, key, attr, value, tmpdir):
        config_file = tmpdir.join("config.yaml")
        with config_file.open("w") as fobj:
            pyaml.dump({key: value}, fobj, safe=True, default_style='"')
        config = Configuration(["--config-file", config_file.strpath])
        assert getattr(config, attr) == value

    def test_host_rewrite_rules(self):
        args = ("pattern=value", "(\d+)\.\example\.com=$1.example.net", "www.([a-z]+.com)={env}.$1")
        config = Configuration(["--host-rewrite-rule=%s" % arg for arg in args])
        assert config.host_rewrite_rules == [HostRewriteRule(arg) for arg in args]

    def test_host_rewrite_rules_from_file(self, tmpdir):
        args = ("pattern=value", "(\d+)\.\example\.com=$1.example.net", "www.([a-z]+.com)={env}.$1")
        config_file = tmpdir.join("config.yaml")
        with config_file.open("w") as fobj:
            pyaml.dump({"host-rewrite-rule": args}, fobj, safe=True, default_style='"')
        config = Configuration(["--config-file", config_file.strpath])
        assert config.host_rewrite_rules == [HostRewriteRule(arg) for arg in args]

    def test_mutually_exclusive_lists(self):
        with pytest.raises(SystemExit):
            Configuration(["--blacklist", "blacklisted", "--whitelist", "whitelisted"])

    def test_global_env_keyvalue(self):
        args = ("pattern=value", "FIAAS_ENV=test")
        config = Configuration(["--global-env=%s" % arg for arg in args])
        assert config.global_env == {KeyValue(arg).key: KeyValue(arg).value for arg in args}


class TestHostRewriteRule(object):
    def test_equality(self):
        arg = "pattern=value"
        assert HostRewriteRule(arg) == HostRewriteRule(arg)

    @pytest.mark.parametrize("rule,host,result", [
        (r"pattern=value", "pattern", "value"),
        (r"www.([a-z]+).com=www.\1.net", "www.example.com", "www.example.net"),
        (r"(?P<name>[a-z_-]+).example.com=\g<name>-stage.route.\g<name>.example.net", "query-manager.example.com",
         "query-manager-stage.route.query-manager.example.net"),
    ])
    def test_apply(self, rule, host, result):
        hrr = HostRewriteRule(rule)
        assert hrr.matches(host)
        assert not hrr.matches("something-else")
        assert hrr.apply(host) == result
