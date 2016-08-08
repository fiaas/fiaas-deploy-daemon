#!/usr/bin/env python
# -*- coding: utf-8
from argparse import Namespace

import configargparse
import os


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
        self._resolve_proxy()

    def _parse_args(self, args):
        parser = configargparse.ArgParser(auto_env_var_prefix="")
        parser.add_argument("--api-server", help="Address of the api-server to use (IP or name)",
                            default="https://kubernetes.default.svc.cluster.local")
        parser.add_argument("--api-token", help="Token to use (default: lookup from service account)",
                            default=None)
        parser.add_argument("--api-cert", help="SSL certificate to use (default: lookup from service account)",
                            default=None)
        parser.add_argument("--log-format", help="Set logformat",
                            choices=self.VALID_LOG_FORMAT, default="plain")
        parser.add_argument("--target-cluster", help="Logical name of cluster to deploy to",
                            env_var="FINN_ENV", default=None)
        parser.add_argument("--proxy", help="Use proxy for requests to pipeline and getting fiaas-artifacts",
                            env_var="HTTP_PROXY", default="http://puppetproxy.finntech.no:42042")
        parser.add_argument("--no-proxy", help="Disable the use of a proxy",
                            action="store_true")
        parser.add_argument("--debug", help="Enable a number of debugging options (including disable SSL-verification)",
                            action="store_true")
        parser.add_argument("--infrastructure",
                            help="The underlying infrastructure of the cluster to deploy to. Must be either diy or gke. (default: diy).",
                            env_var="FIAAS_INFRASTRUCTURE",
                            choices=("diy", "gke"), default="diy")
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

    def _resolve_proxy(self):
        if self.no_proxy:
            self.proxy = ""

    def has_service(self, service):
        try:
            self.resolve_service(service)
        except InvalidConfigurationException:
            return False
        return True

    def resolve_service(self, service):
        host = self._resolve_required_variable("{}_SERVICE_HOST".format(service.upper()), service)
        port_key = "{}_SERVICE_PORT".format(service.upper())
        port = self._resolve_required_variable(port_key, service)
        try:
            port = int(port)
        except ValueError:
            raise InvalidConfigurationException(
                    "{} is not set to a port-number, but instead {!r}. Unable to resolve service {}".format(port_key, port, service))
        return host, port

    @staticmethod
    def _resolve_required_variable(key, service):
        value = os.getenv(key)
        if not value:
            raise InvalidConfigurationException("{} is not set in environment, unable to resolve service {}".format(key, service))
        return value

    def __repr__(self):
        return "Configuration({})".format(
                ", ".join("{}={}".format(key, self.__dict__[key]) for key in vars(self)
                          if not key.startswith("_") and not key.isupper() and "token" not in key)
        )


class InvalidConfigurationException(Exception):
    pass
