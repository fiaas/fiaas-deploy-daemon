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
import pyaml
import pytest

from fiaas_deploy_daemon.config import Configuration, HostRewriteRule, KeyValue, InvalidConfigurationException


class TestConfig(object):

    @pytest.fixture
    def getenv(self):
        with mock.patch("os.getenv") as getenv:
            yield getenv

    @pytest.fixture
    def namespace_file_does_not_exist(self):
        with mock.patch("__builtin__.open", new_callable=mock.mock_open) as _open:
            _open.side_effect = IOError("does not exist")
            yield _open

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
        assert config.enable_deprecated_multi_namespace_support is False
        assert config.enable_deprecated_tls_entry_per_host is False
        assert config.disable_deprecated_managed_env_vars is False
        assert config.tls_certificate_ready is False

    @pytest.mark.parametrize("arg,key", [
        ("--api-server", "api_server"),
        ("--api-token", "api_token"),
        ("--api-cert", "api_cert"),
        ("--environment", "environment"),
        ("--proxy", "proxy"),
        ("--strongbox-init-container-image", "strongbox_init_container_image"),
    ])
    def test_parameters(self, arg, key):
        config = Configuration([arg, "value"])

        assert getattr(config, key) == "value"

    def test_infrastructure_param(self):
        config = Configuration(["--infrastructure", "gke"])

        assert config.infrastructure == "gke"

    @pytest.mark.parametrize("key", (
        "debug",
        "enable_crd_support",
        "enable_deprecated_multi_namespace_support",
        "enable_deprecated_tls_entry_per_host",
        "disable_crd_creation",
        "datadog_activate_sleep"
    ))
    def test_flags(self, key):
        flag = "--{}".format(key.replace("_", "-"))
        config = Configuration([])
        assert getattr(config, key) is False
        config = Configuration([flag])
        assert getattr(config, key) is True

    @pytest.mark.parametrize("key,attr,value", [
        ("environment", "environment", "gke"),
        ("proxy", "proxy", "http://proxy.example.com"),
        ("ingress-suffix", "ingress_suffixes", [r"1\.example.com", "2.example.com"]),
        ("strongbox-init-container-image", "strongbox_init_container_image", "fiaas/strongbox-image-test:123"),
        ("extension-hook-url", "extension_hook_url", "hook-service-url"),
    ])
    def test_config_from_file(self, key, attr, value, tmpdir):
        config_file = tmpdir.join("config.yaml")
        with config_file.open("w") as fobj:
            pyaml.dump({key: value}, fobj, safe=True, default_style='"')
        config = Configuration(["--config-file", config_file.strpath])
        assert getattr(config, attr) == value

    def test_host_rewrite_rules(self):
        args = ("pattern=value", r"(\d+)\.\example\.com=$1.example.net", "www.([a-z]+.com)={env}.$1")
        config = Configuration(["--host-rewrite-rule=%s" % arg for arg in args])
        assert config.host_rewrite_rules == [HostRewriteRule(arg) for arg in args]

    def test_host_rewrite_rules_from_file(self, tmpdir):
        args = ("pattern=value", r"(\d+)\.\example\.com=$1.example.net", "www.([a-z]+.com)={env}.$1")
        config_file = tmpdir.join("config.yaml")
        with config_file.open("w") as fobj:
            pyaml.dump({"host-rewrite-rule": args}, fobj, safe=True, default_style='"')
        config = Configuration(["--config-file", config_file.strpath])
        assert config.host_rewrite_rules == [HostRewriteRule(arg) for arg in args]

    def test_global_env_keyvalue(self):
        args = ("pattern=value", "FIAAS_ENV=test")
        config = Configuration(["--global-env=%s" % arg for arg in args])
        assert config.global_env == {KeyValue(arg).key: KeyValue(arg).value for arg in args}

    def test_resolve_namespace_file_should_take_precedence_over_env(self):
        config = Configuration([])
        assert config.namespace == "namespace-from-file"

    @pytest.mark.usefixtures("namespace_file_does_not_exist")
    def test_resolve_namespace_env_should_be_used_if_unable_to_open_file(self, getenv):
        expected = "namespace-from-env"
        getenv.side_effect = lambda key: expected if key == "NAMESPACE" else None

        config = Configuration([])
        assert config.namespace == expected

    @pytest.mark.usefixtures("namespace_file_does_not_exist")
    def test_resolve_namespace_raise_if_unable_to_open_file_and_no_env_var(self, getenv):
        getenv.return_value = None
        with pytest.raises(InvalidConfigurationException):
            Configuration([])

    def test_behavior_for_undefined_flags_in_config_yml(self, tmpdir):
        config_flags = {
            "undefined_configuration_parameter": "a value",
            "debug": "true",
        }
        config_file = tmpdir.join("config.yaml")
        with config_file.open("w") as fobj:
            pyaml.dump(config_flags, fobj, safe=True, default_style='"')
        config = Configuration(["--config-file", config_file.strpath])
        # Defined configuration flags should be set
        assert config.debug is True
        # Undefined configuration flags should not be available
        with pytest.raises(AttributeError):
            config.undefined_configuration_parameter

    def test_datadog_global_tags_keyvalue(self):
        args = ("pattern=value", "FIAAS_DD_tag=test")
        config = Configuration(["--datadog-global-tags=%s" % arg for arg in args])
        assert config.datadog_global_tags == {KeyValue(arg).key: KeyValue(arg).value for arg in args}

    def test_tls_issuers(self):
        issuer_types = ["foo.bar.com=issuer", "woo.foo.bar.com=other"]
        args = ["--tls-certificate-issuer-type-overrides=%s" % issuer_type for issuer_type in issuer_types]
        config = Configuration(args)
        assert config.tls_certificate_issuer_type_overrides == {
            "foo.bar.com": "issuer",
            "woo.foo.bar.com": "other"
        }


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
