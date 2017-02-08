#!/usr/bin/env python
# -*- coding: utf-8
from argparse import Namespace

import configargparse
import dns.resolver
import os
import logging


class Configuration(Namespace):
    VALID_LOG_FORMAT = ("plain", "json")
    WTF_CSRF_ENABLED = False

    def __init__(self, args=None, **kwargs):
        super(Configuration, self).__init__(**kwargs)
        self.image = ""
        self.version = ""
        self.SECRET_KEY = os.urandom(24)
        self._parse_args(args)
        self._resolve_api_config()
        self._resolve_env()
        self._logger = logging.getLogger(__name__)

    def _parse_args(self, args):
        parser = configargparse.ArgParser(auto_env_var_prefix="",
                                          add_config_file_help=True,
                                          add_env_var_help=True,
                                          config_file_parser_class=configargparse.YAMLConfigFileParser,
                                          default_config_files=["/var/run/config/fiaas/cluster_config.yaml"],
                                          args_for_setting_config_path=["-c", "--config-file"],
                                          ignore_unknown_config_file_keys=True,
                                          formatter_class=configargparse.ArgumentDefaultsHelpFormatter)
        parser.add_argument("--api-server", help="Address of the api-server to use (IP or name)",
                            default="https://kubernetes.default.svc.cluster.local")
        parser.add_argument("--api-token", help="Token to use (default: lookup from service account)",
                            default=None)
        parser.add_argument("--api-cert", help="SSL certificate to use (default: lookup from service account)",
                            default=None)
        parser.add_argument("--client-cert", help="Client certificate to use",
                            default=None)
        parser.add_argument("--client-key", help="Client certificate key to use",
                            default=None)
        parser.add_argument("--log-format", help="Set logformat (default: %(default)s)",
                            choices=self.VALID_LOG_FORMAT, default="plain")
        parser.add_argument("--proxy", help="Use proxy for requests to pipeline and getting fiaas-artifacts",
                            env_var="http_proxy")
        parser.add_argument("--debug", help="Enable a number of debugging options (including disable SSL-verification)",
                            action="store_true")
        parser.add_argument("--environment", help="Environment to deploy to",
                            env_var="FIAAS_ENVIRONMENT", default="")
        parser.add_argument("--ingress-suffix", help="Suffix to use for ingress", action="append",
                            dest="ingress_suffixes", env_var="INGRESS_SUFFIX", default=[])
        parser.add_argument("--infrastructure",
                            help="The underlying infrastructure of the cluster to deploy to. (default: %(default)s).",
                            env_var="FIAAS_INFRASTRUCTURE", choices=("diy", "gke"), default="diy")
        parser.add_argument("--port", help="Port to use for the web-interface (default: %(default)s)", type=int,
                            default=5000)
        parser.parse_args(args, namespace=self)

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

    def has_service(self, service):
        try:
            self.resolve_service(service)
        except InvalidConfigurationException:
            return False
        return True

    def resolve_service(self, service):
        try:
            return self._resolve_service_from_srv_record(service)
        except dns.resolver.NXDOMAIN as e:
            self._logger.warn("Failed to lookup SRV. %s", str(e))
        return self._resolve_service_from_env(service)

    def _resolve_service_from_srv_record(self, service):
        srv = "_{}._tcp.{}".format(service, service)
        answers = dns.resolver.query(srv, 'SRV')
        # SRV target: the canonical hostname of the machine providing the service, ending in a dot.
        return str(answers[0].target)[:-1], answers[0].port

    def _resolve_service_from_env(self, service):
        host = self._resolve_required_variable("{}_SERVICE_HOST".format(service.upper()), service)
        port_key = "{}_SERVICE_PORT".format(service.upper())
        port = self._resolve_required_variable(port_key, service)
        try:
            port = int(port)
        except ValueError:
            raise InvalidConfigurationException(
                "{} is not set to a port-number, but instead {!r}. Unable to resolve service {}".format(port_key, port,
                                                                                                        service))
        return host, port

    @staticmethod
    def _resolve_required_variable(key, service):
        value = os.getenv(key)
        if not value:
            raise InvalidConfigurationException(
                "{} is not set in environment, unable to resolve service {}".format(key, service))
        return value

    def __repr__(self):
        return "Configuration({})".format(
            ", ".join("{}={}".format(key, self.__dict__[key]) for key in vars(self)
                      if not key.startswith("_") and not key.isupper() and "token" not in key)
        )


class InvalidConfigurationException(Exception):
    pass
