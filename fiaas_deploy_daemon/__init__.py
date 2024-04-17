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
import signal
import sys
import threading
import traceback
from queue import Queue

import pinject
import requests
from k8s import config as k8s_config
from prometheus_client import Info

from .config import Configuration
from .crd import CustomResourceDefinitionBindings, DisabledCustomResourceDefinitionBindings
from .deployer import DeployerBindings
from .deployer.kubernetes import K8sAdapterBindings
from .extension_hook_caller import ExtensionHookCaller
from .lifecycle import Lifecycle
from .logsetup import init_logging
from .secrets import resolve_secrets
from .specs import SpecBindings
from .tools import log_request_response
from .usage_reporting import UsageReportingBindings
from .web import WebBindings


class MainBindings(pinject.BindingSpec):
    def __init__(self, config: Configuration):
        self._config = config
        self._deploy_queue = Queue()

    def configure(self, bind):
        bind("config", to_instance=self._config)
        bind("deploy_queue", to_instance=self._deploy_queue)
        bind("health_check", to_class=HealthCheck)
        bind("lifecycle", to_class=Lifecycle)
        bind("extension_hook", to_class=ExtensionHookCaller)

    def provide_session(self, config: Configuration):
        session = requests.Session()
        if config.proxy:
            session.proxies = {scheme: config.proxy for scheme in ("http", "https")}
        if config.debug:
            session.hooks["response"].append(log_request_response)
        return session

    def provide_secrets(self, config: Configuration):
        return resolve_secrets(config.secrets_directory)


class HealthCheck(object):
    @pinject.copy_args_to_internal_fields
    def __init__(self, deployer, scheduler, crd_watcher, usage_reporter):
        pass

    def is_healthy(self):
        return all(
            (
                self._deployer.is_alive(),
                self._scheduler.is_alive(),
                self._crd_watcher.is_alive(),
                self._usage_reporter.is_alive(),
            )
        )


class Main(object):
    @pinject.copy_args_to_internal_fields
    def __init__(self, deployer, scheduler, webapp, config, crd_watcher, usage_reporter):
        pass

    def run(self):
        self._deployer.start()
        self._scheduler.start()
        self._crd_watcher.start()
        self._usage_reporter.start()
        # Run web-app in main thread
        self._webapp.run("0.0.0.0", self._config.port)


def init_k8s_client(config: Configuration, log: logging.Logger):
    if config.client_cert:
        k8s_config.cert = (config.client_cert, config.client_key)

    if config.api_token:
        k8s_config.api_token = config.api_token
    else:
        # use default in-cluster config if api_token is not explicitly set
        try:
            # sets api_token_source and verify_ssl
            k8s_config.use_in_cluster_config()
        except IOError as e:
            if not config.client_cert:
                log.warning("No apiserver auth config was specified, and in-cluster config could not be set up: %s", str(e))

    # if api_cert or debug is explicitly set, override in-cluster config setting (if used)
    if config.api_cert:
        k8s_config.verify_ssl = config.api_cert
    elif config.debug:
        k8s_config.verify_ssl = not config.debug

    k8s_config.api_server = config.api_server
    k8s_config.debug = config.debug


def thread_dump_logger(log: logging.Logger):
    def _dump_threads(signum, frame):
        log.info("Received signal %s, dumping thread stacks", signum)
        thread_names = {t.ident: t.name for t in threading.enumerate()}
        for thread_ident, frame in list(sys._current_frames().items()):
            log.info("Thread ident=0x%x name=%s", thread_ident, thread_names.get(thread_ident, "unknown"))
            log.info("".join(traceback.format_stack(frame)))

    return _dump_threads


def warn_if_env_variable_config(config, log):
    """temporary deprecation warning for https://github.com/fiaas/fiaas-deploy-daemon/issues/12"""

    configuration_env_variable_keys = {
        "SECRETS_DIRECTORY",
        "LOG_FORMAT",
        "http_proxy",
        "DEBUG",
        "FIAAS_ENVIRONMENT",
        "FIAAS_SERVICE_TYPE",
        "FIAAS_INFRASTRUCTURE",
        "PORT",
        "ENABLE_CRD_SUPPORT",
        "SECRETS_INIT_CONTAINER_IMAGE",
        "SECRETS_SERVICE_ACCOUNT_NAME",
        "DATADOG_CONTAINER_IMAGE",
        "DATADOG_CONTAINER_MEMORY",
        "FIAAS_DATADOG_GLOBAL_TAGS",
        "PRE_STOP_DELAY",
        "STRONGBOX_INIT_CONTAINER_IMAGE",
        "ENABLE_DEPRECATED_MULTI_NAMESPACE_SUPPORT",
        "USE_INGRESS_TLS",
        "TLS_CERTIFICATE_ISSUER",
        "USE_IN_MEMORY_EMPTYDIRS",
        "DEPLOYMENT_MAX_SURGE",
        "DEPLOYMENT_MAX_UNAVAILABLE",
        "READY_CHECK_TIMEOUT_MULTIPLIER",
        "DISABLE_DEPRECATED_MANAGED_ENV_VARS",
        "USAGE_REPORTING_CLUSTER_NAME",
        "USAGE_REPORTING_OPERATOR",
        "USAGE_REPORTING_ENDPOINT",
        "USAGE_REPORTING_TENANT",
        "USAGE_REPORTING_TEAM",
        "API_SERVER",
        "API_TOKEN",
        "API_CERT",
        "CLIENT_CERT",
        "CLIENT_KEY",
        "INGRESS_SUFFIXES",
        "HOST_REWRITE_RULES",
        "FIAAS_GLOBAL_ENV",
        "FIAAS_SECRET_INIT_CONTAINERS",
    }
    environ_keys = set(os.environ.keys())
    possible_config_env_variables = sorted(configuration_env_variable_keys & environ_keys)
    if len(possible_config_env_variables) > 0:
        log.warning(
            "found configuration environment variables %s. The ability to configure fiaas-deploy-daemon via environment variables "
            + "has been removed. If you are trying to use these environment variables to configure fiaas-deploy-daemon, "
            + "that configuration will not take effect. Please switch to configuring via a config file/ConfigMap or command-line "
            + "flags. See https://github.com/fiaas/fiaas-deploy-daemon/issues/12 for more information.",
            ", ".join(possible_config_env_variables),
        )


def expose_fdd_version(config: Configuration):
    i = Info("fiaas_fdd_version", "The tag of the running fiaas-deploy-daemon docker image.")
    i.info({"fiaas_fdd_version": config.version})


def main():
    cfg = Configuration()
    init_logging(cfg)
    log = logging.getLogger(__name__)
    init_k8s_client(cfg, log)
    warn_if_env_variable_config(cfg, log)
    expose_fdd_version(cfg)
    signal.signal(signal.SIGUSR2, thread_dump_logger(log))

    try:
        log.info("fiaas-deploy-daemon starting with configuration {!r}".format(cfg))
        if cfg.enable_crd_support:
            crd_binding = CustomResourceDefinitionBindings(cfg.use_apiextensionsv1_crd, cfg.include_status_in_app)
        else:
            crd_binding = DisabledCustomResourceDefinitionBindings()
        binding_specs = [
            MainBindings(cfg),
            DeployerBindings(),
            K8sAdapterBindings(cfg.use_networkingv1_ingress),
            WebBindings(),
            SpecBindings(),
            crd_binding,
            UsageReportingBindings(),
        ]
        obj_graph = pinject.new_object_graph(modules=None, binding_specs=binding_specs)
        obj_graph.provide(Main).run()
    except BaseException:
        log.exception("General failure! Inspect traceback and make the code better!")


if __name__ == "__main__":
    main()
