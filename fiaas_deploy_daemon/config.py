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
import logging
import os
import re
from argparse import Namespace

import configargparse

DEFAULT_CONFIG_FILE = "/var/run/config/fiaas/cluster_config.yaml"
DEFAULT_SECRETS_DIR = "/var/run/secrets/fiaas/"

INGRESS_SUFFIX_LONG_HELP = """
When creating Ingress objects for an application, a host may be specified,
which will be used to match the request with the application. For each
ingress suffix specified in the configuration, a host section is generated
for the application in the form `<application name>.<ingress suffix>`.

If the application specifies a `host` in its configuration, a section for
that host will be generated *in addition* to the sections generated for
each ingress suffix.
"""

HOST_REWRITE_RULE_LONG_HELP = """
An application has the option of specifying a `host` in its configuration.
This host might not be useful in all clusters, due to DNS outside the cluster
or other reasons outside the control of the cluster. To make this work,
a number of host-rewrite-rules may be specified. Each rule consists of a
regex pattern, and a replacement value. The `host` is matched against each
pattern in the order given, stopping at the first match. The replacement can
contain groups using regular regex replace syntax.

Regardless of how a rule is passed in (option, environment variable or in
a config file), it must be specified as `<pattern>=<replacement>`. In
particular, be aware that even if it would be natural to use the map type
in YAML, this is not possible.

See <https://docs.python.org/2.7/library/re.html#regular-expression-syntax>.
"""

GLOBAL_ENV_LONG_HELP = """
If you wish to expose certain environment variables to every application
in your cluster, define them here.

Regardless of how a variable is passed in (option, environment variable or in
a config file), it must be specified as `<key>=<value>`.
"""

USAGE_REPORTING_LONG_HELP = """
FIAAS can optionally report usage data to a web-service via POSTs to an
HTTP endpoint. Fiaas-deploy-daemon will POST a json structure to the endpoint
on deployment start, deployment failure and deployment success.
"""

MULTI_NAMESPACE_HELP = """
Make fiaas-deploy-daemon watch for TPRs and/or CRDs and execute deployments in all namespaces. The default behavior is
 to only watch the namespace fiaas-deploy-daemon runs in. This feature is deprecated and will soon be removed."""

TLS_HELP = """
Enable fiaas-deploy-daemon to extend ingress objects to support https.

Option `default_on` will, when creating ingress objects for an application, enable https unless explicitly set to
disabled in the configuration for an application.

Option `default_off` will, when creating ingress objects for an application, not enable https unless explicitly set
to enabled in the configuration for an application.

Option `disabled` (the default value) will not enable https at all when creating ingress objects for an application,
ignoring any relevant options set in the configuration for an application.
"""

TLS_ENTRY_PER_HOST_HELP = """
When using extensions.tls, add a separate TLS entry for each host in addition to the default TLS entry for the
application containing all hosts. This feature is deprecated and will soon be removed.
"""

EPILOG = """
Args that start with '--' (eg. --log-format) can also be set in a config file
({} or specified via -c). The config file uses YAML syntax and must represent
a YAML 'mapping' (for details, see http://learn.getgrav.org/advanced/yaml).

It is possible to specify '--ingress-suffix' and '--host-rewrite-rule' multiple times to add more than one of each.
In the config-file, these should be defined as a YAML list
(see https://github.com/bw2/ConfigArgParse#special-values).

If an arg is specified in more than one place, then commandline values
override environment variables which override config file values which
override defaults.
""".format(DEFAULT_CONFIG_FILE)

DATADOG_GLOBAL_TAGS_LONG_HELP = """
If you wish to send certain tags to datadog in every application
in your cluster, define them here.

Regardless of how a variable is passed in (option, environment variable or in
a config file), it must be specified as `<key>=<value>`.
"""

SECRET_CONTAINERS_LONG_HELP = """
You can register container-images that can be used as secret init-containers
by applications. Specify as `type=image`, and then reference this in the
application config as `extensions.secrets.<type>`.

Using 'default' as the 'type' will mean the container will be attached automatically,
if the application doesn't specify any.
"""


class Configuration(Namespace):
    VALID_LOG_FORMAT = ("plain", "json")

    def __init__(self, args=None, **kwargs):
        super(Configuration, self).__init__(**kwargs)
        self._logger = logging.getLogger(__name__)
        self.image = ""
        self.version = ""
        self._parse_args(args)
        self._resolve_api_config()
        self._resolve_env()
        self.namespace = self._resolve_namespace()

    def _parse_args(self, args):
        parser = configargparse.ArgParser(auto_env_var_prefix="",
                                          add_config_file_help=False,
                                          add_env_var_help=False,
                                          config_file_parser_class=configargparse.YAMLConfigFileParser,
                                          default_config_files=[DEFAULT_CONFIG_FILE],
                                          args_for_setting_config_path=["-c", "--config-file"],
                                          ignore_unknown_config_file_keys=True,
                                          description="%(prog)s deploys applications to Kubernetes",
                                          epilog=EPILOG,
                                          formatter_class=configargparse.ArgumentDefaultsHelpFormatter)
        parser.add_argument("--secrets-directory", help="Load secrets from this directory (default: %(default)s)",
                            default=DEFAULT_SECRETS_DIR)
        parser.add_argument("--log-format", help="Set logformat (default: %(default)s)", choices=self.VALID_LOG_FORMAT,
                            default="plain")
        parser.add_argument("--proxy", help="Use http proxy (currently only used for for usage reporting)",
                            env_var="http_proxy")
        parser.add_argument("--debug", help="Enable a number of debugging options (including disable SSL-verification)",
                            action="store_true")
        parser.add_argument("--environment", help="Environment to deploy to", env_var="FIAAS_ENVIRONMENT", default="")
        parser.add_argument("--service-type", help="Type of kubernetes Service to create", env_var="FIAAS_SERVICE_TYPE",
                            choices=("ClusterIP", "NodePort", "LoadBalancer"), default="ClusterIP")
        parser.add_argument("--infrastructure",
                            help="The underlying infrastructure of the cluster to deploy to. (default: %(default)s).",
                            env_var="FIAAS_INFRASTRUCTURE", choices=("diy", "gke"), default="diy")
        parser.add_argument("--port", help="Port to use for the web-interface (default: %(default)s)", type=int,
                            default=5000)
        parser.add_argument("--enable-crd-support", help="Enable Custom Resource Definition support.",
                            action="store_true")
        parser.add_argument("--secrets-init-container-image",
                            help="Use specified docker image as init container for secrets (experimental)",
                            default=None)
        parser.add_argument("--secrets-service-account-name",
                            help="The service account that is passed to secrets init containers", default=None)
        parser.add_argument("--datadog-container-image",
                            help="Use specified docker image as datadog sidecar for apps", default=None)
        parser.add_argument("--datadog-container-memory",
                            help="The amount of memory (request and limit) for the datadog sidecar", default="2Gi")
        datadog_global_tags_parser = parser.add_argument_group("Datadog Global tags", DATADOG_GLOBAL_TAGS_LONG_HELP)
        datadog_global_tags_parser.add_argument("--datadog-global-tags", default=[],
                                                env_var="FIAAS_DATADOG_GLOBAL_TAGS",
                                                help="Various non-essential global tags to send to datadog for all applications",
                                                action="append", type=KeyValue, dest="datadog_global_tags")
        parser.add_argument("--pre-stop-delay", type=int,
                            help="Add a pre-stop hook that sleeps for this amount of seconds  (default: %(default)s)",
                            default=0)
        parser.add_argument("--strongbox-init-container-image",
                            help="Use specified docker image as init container for apps that are configured to use Strongbox",
                            default=None)
        parser.add_argument("--enable-deprecated-multi-namespace-support", help=MULTI_NAMESPACE_HELP,
                            action="store_true")
        parser.add_argument("--use-ingress-tls", help=TLS_HELP,
                            choices=("disabled", "default_off", "default_on"),
                            default="disabled")
        parser.add_argument("--tls-certificate-issuer", help="Certificate issuer to use with cert-manager to provision certificates",
                            default=None)
        parser.add_argument("--use-in-memory-emptydirs", help="Use memory for emptydirs mounted in the deployed application",
                            action="store_true")
        parser.add_argument("--deployment-max-surge", help="maximum number of extra pods that can be scheduled above the desired "
                            "number of pods during an update",
                            default=u"25%", type=_int_or_unicode)
        parser.add_argument("--deployment-max-unavailable", help="The maximum number of pods that can be unavailable during an update",
                            default="0", type=_int_or_unicode)
        parser.add_argument("--enable-deprecated-tls-entry-per-host", help=TLS_ENTRY_PER_HOST_HELP,
                            action="store_true")
        parser.add_argument("--ready-check-timeout-multiplier", type=int,
                            help="Multiply default ready check timeout (replicas * initialDelaySeconds) with this " +
                                 "number of seconds  (default: %(default)s)", default=10)
        usage_reporting_parser = parser.add_argument_group("Usage Reporting", USAGE_REPORTING_LONG_HELP)
        usage_reporting_parser.add_argument("--usage-reporting-cluster-name",
                                            help="Name of the cluster where the fiaas-deploy-daemon instance resides")
        usage_reporting_parser.add_argument("--usage-reporting-operator",
                                            help="Identifier for the operator of the fiaas-deploy-daemon instance")
        usage_reporting_parser.add_argument("--usage-reporting-endpoint", help="Endpoint to POST usage data to")
        usage_reporting_parser.add_argument("--usage-reporting-tenant", help="Name of publisher of events")
        usage_reporting_parser.add_argument("--usage-reporting-team",
                                            help="""Name of team that is responsible for components deployed \
                                                 "by the fiaas-deploy-daemon instance""")
        api_parser = parser.add_argument_group("API server")
        api_parser.add_argument("--api-server", help="Address of the api-server to use (IP or name)",
                                default="https://kubernetes.default.svc.cluster.local")
        api_parser.add_argument("--api-token", help="Token to use (default: lookup from service account)", default=None)
        api_parser.add_argument("--api-cert", help="API server certificate (default: lookup from service account)",
                                default=None)
        client_cert_parser = parser.add_argument_group("Client certificate")
        client_cert_parser.add_argument("--client-cert", help="Client certificate to use", default=None)
        client_cert_parser.add_argument("--client-key", help="Client certificate key to use", default=None)
        ingress_parser = parser.add_argument_group("Ingress suffix", INGRESS_SUFFIX_LONG_HELP)
        ingress_parser.add_argument("--ingress-suffix", help="Suffix to use for ingress", action="append",
                                    dest="ingress_suffixes", env_var="INGRESS_SUFFIXES", default=[])
        host_rule_parser = parser.add_argument_group("Host rewrite rules", HOST_REWRITE_RULE_LONG_HELP)
        host_rule_parser.add_argument("--host-rewrite-rule", help="Rule for rewriting host", action="append",
                                      type=HostRewriteRule, dest="host_rewrite_rules", env_var="HOST_REWRITE_RULES",
                                      default=[])
        global_env_parser = parser.add_argument_group("Global environment variables", GLOBAL_ENV_LONG_HELP)
        global_env_parser.add_argument("--global-env", default=[], env_var="FIAAS_GLOBAL_ENV",
                                       help="Various non-essential global variables to expose for all applications",
                                       action="append", type=KeyValue, dest="global_env")
        secret_init_containers_parser = parser.add_argument_group("Secret init-containers", SECRET_CONTAINERS_LONG_HELP)
        secret_init_containers_parser.add_argument("--secret-init-containers", default=[],
                                                   env_var="FIAAS_SECRET_INIT_CONTAINERS",
                                                   help="Images to use for secret init-containers by key",
                                                   action="append", type=KeyValue, dest="secret_init_containers")
        parser.parse_args(args, namespace=self)
        self.global_env = {env_var.key: env_var.value for env_var in self.global_env}
        self.datadog_global_tags = {tag.key: tag.value for tag in self.datadog_global_tags}
        self.secret_init_containers = {provider.key: provider.value for provider in self.secret_init_containers}

    def _resolve_api_config(self):
        token_file = "/var/run/secrets/kubernetes.io/serviceaccount/token"
        if os.path.exists(token_file):
            with open(token_file) as fobj:
                self.api_token = fobj.read().strip()
            self.api_cert = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"

    def _resolve_env(self):
        image = os.getenv("IMAGE")
        if image:
            self.image = image
        version = os.getenv("VERSION")
        if version:
            self.version = version

    @staticmethod
    def _resolve_required_variable(key, service_name):
        value = os.getenv(key)
        if not value:
            raise InvalidConfigurationException(
                "{} is not set in environment, unable to resolve service {}".format(key, service_name))
        return value

    @staticmethod
    def _resolve_namespace():
        namespace_file_path = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
        namespace_env_variable = "NAMESPACE"
        try:
            with open(namespace_file_path, 'r') as fobj:
                namespace = fobj.read().strip()
                if namespace:
                    return namespace
        except IOError:
            namespace = os.getenv(namespace_env_variable)
            if namespace:
                return namespace
        raise InvalidConfigurationException(
            "Could not determine namespace: could not read {path}, and ${env_var} was not set".format(
                path=namespace_file_path, env_var=namespace_env_variable))

    def __repr__(self):
        return "Configuration({})".format(
            ", ".join("{}={}".format(key, self.__dict__[key]) for key in vars(self)
                      if not key.startswith("_") and not key.isupper() and "token" not in key)
        )


class KeyValue(object):
    def __init__(self, arg):
        self.key, self.value = arg.split("=")

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return other.key == self.key and other.value == self.value


class HostRewriteRule(object):
    def __init__(self, arg):
        pattern, self._replacement = arg.split("=")
        self._pattern = re.compile(pattern)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return other._pattern.pattern == self._pattern.pattern and other._replacement == self._replacement

    def matches(self, host):
        return self._pattern.match(host)

    def apply(self, host):
        return self._pattern.sub(self._replacement, host)


class InvalidConfigurationException(Exception):
    pass


def _int_or_unicode(arg):
    """Accept a number or a (unicode) string, but not a number as a string"""
    try:
        return int(arg)
    except ValueError:
        return unicode(arg)
