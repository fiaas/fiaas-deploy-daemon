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
from __future__ import absolute_import

import logging
import os
import signal
import sys
import threading
import traceback
from Queue import Queue

import pinject
import requests
from k8s import config as k8s_config

from .config import Configuration
from .crd import CustomResourceDefinitionBindings, DisabledCustomResourceDefinitionBindings
from .deployer import DeployerBindings
from .deployer.kubernetes import K8sAdapterBindings
from .lifecycle import Lifecycle
from .logsetup import init_logging
from .secrets import resolve_secrets
from .specs import SpecBindings
from .tools import log_request_response
from .usage_reporting import UsageReportingBindings
from .web import WebBindings


class MainBindings(pinject.BindingSpec):
    def __init__(self, config):
        self._config = config
        self._deploy_queue = Queue()

    def configure(self, bind):
        bind("config", to_instance=self._config)
        bind("deploy_queue", to_instance=self._deploy_queue)
        bind("health_check", to_class=HealthCheck)
        bind("lifecycle", to_class=Lifecycle)

    def provide_session(self, config):
        session = requests.Session()
        if config.proxy:
            session.proxies = {scheme: config.proxy for scheme in (
                "http",
                "https"
            )}
        if config.debug:
            session.hooks["response"].append(log_request_response)
        return session

    def provide_secrets(self, config):
        return resolve_secrets(config.secrets_directory)


class HealthCheck(object):
    @pinject.copy_args_to_internal_fields
    def __init__(self, deployer, scheduler, crd_watcher, usage_reporter):
        pass

    def is_healthy(self):
        return all((
            self._deployer.is_alive(),
            self._scheduler.is_alive(),
            self._crd_watcher.is_alive(),
            self._usage_reporter.is_alive(),
        ))


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


def init_k8s_client(config):
    k8s_config.api_server = config.api_server
    k8s_config.api_token = config.api_token
    if config.api_cert:
        k8s_config.verify_ssl = config.api_cert
    else:
        k8s_config.verify_ssl = not config.debug
    if config.client_cert:
        k8s_config.cert = (config.client_cert, config.client_key)
    k8s_config.debug = config.debug


def thread_dump_logger(log):
    def _dump_threads(signum, frame):
        log.info("Received signal %s, dumping thread stacks", signum)
        thread_names = {t.ident: t.name for t in threading.enumerate()}
        for thread_ident, frame in sys._current_frames().items():
            log.info("Thread ident=0x%x name=%s", thread_ident, thread_names.get(thread_ident, "unknown"))
            log.info("".join(traceback.format_stack(frame)))

    return _dump_threads


def warn_if_env_variable_config(config, log):
    """temporary deprecation warning for https://github.com/fiaas/fiaas-deploy-daemon/issues/12"""
    configuration_env_variables = {
        'secrets_directory': config.secrets_directory,
        'log_format': config.log_format,
        'http_proxy': config.proxy,
        'debug': config.debug,
        'FIAAS_ENVIRONMENT': config.environment,
        'FIAAS_SERVICE_TYPE': config.service_type,
        'FIAAS_INFRASTRUCTURE': config.infrastructure,
        'port': config.port,
        'enable_crd_support': config.enable_crd_support,
        'secrets_init_container_image': config.secrets_init_container_image,
        'secrets_service_account_name': config.secrets_service_account_name,
        'datadog_container_image': config.datadog_container_image,
        'datadog_container_memory': config.datadog_container_memory,
        'FIAAS_DATADOG_GLOBAL_TAGS': ','.join('{}={}'.format(k, v) for k, v in config.datadog_global_tags.items()),
        'pre_stop_delay': config.pre_stop_delay,
        'strongbox_init_container_image': config.strongbox_init_container_image,
        'enable_deprecated_multi_namespace_support': config.enable_deprecated_multi_namespace_support,
        'use_ingress_tls': config.use_ingress_tls,
        'tls_certificate_issuer': config.tls_certificate_issuer,
        'use_in_memory_emptydirs': config.use_in_memory_emptydirs,
        'deployment_max_surge': config.deployment_max_surge,
        'deployment_max_unavailable': config.deployment_max_unavailable,
        'ready_check_timeout_multiplier': config.ready_check_timeout_multiplier,
        'disable_deprecated_managed_env_vars': config.disable_deprecated_managed_env_vars,
        'usage_reporting_cluster_name': config.usage_reporting_cluster_name,
        'usage_reporting_endpoint': config.usage_reporting_endpoint,
        'usage_reporting_tenant': config.usage_reporting_tenant,
        'usage_reporting_team': config.usage_reporting_team,
        'api_server': config.api_server,
        'api_token': config.api_token,
        'api_cert': config.api_cert,
        'client_cert': config.client_cert,
        'client_key': config.client_key,
        'INGRESS_SUFFIXES': ','.join(config.ingress_suffixes),
        'HOST_REWRITE_RULES': ','.join(config.host_rewrite_rules),
        'FIAAS_GLOBAL_ENV':  ','.join('{}={}'.format(k, v) for k, v in config.global_env.items()),
        'FIAAS_SECRET_INIT_CONTAINERS': ','.join('{}={}'.format(k, v) for k, v in config.secret_init_containers.items()),
    }
    not_defined = object()  # some config options default to None, avoid false positives when evironment variable is not set
    possible_config_env_variables = [key for key, value in configuration_env_variables.items() if os.getenv(key, not_defined) == value]
    if len(possible_config_env_variables) > 0:
        log.warn("found configuration environment variables %s. The ability to configure fiaas-deploy-daemon via environment variables " +
                 "will be removed. If these environment variables are the primary source for this configuration, please switch to " +
                 "configuring via a config file/ConfigMap or command-line flags. See " +
                 "https://github.com/fiaas/fiaas-deploy-daemon/issues/12 for more information", ', '.join(possible_config_env_variables))


def main():
    cfg = Configuration()
    init_logging(cfg)
    init_k8s_client(cfg)
    log = logging.getLogger(__name__)
    warn_if_env_variable_config(cfg, log)
    signal.signal(signal.SIGUSR2, thread_dump_logger(log))
    try:
        log.info("fiaas-deploy-daemon starting with configuration {!r}".format(cfg))
        binding_specs = [
            MainBindings(cfg),
            DeployerBindings(),
            K8sAdapterBindings(),
            WebBindings(),
            SpecBindings(),
            CustomResourceDefinitionBindings() if cfg.enable_crd_support else DisabledCustomResourceDefinitionBindings(),
            UsageReportingBindings(),
        ]
        obj_graph = pinject.new_object_graph(modules=None, binding_specs=binding_specs)
        obj_graph.provide(Main).run()
    except BaseException:
        log.exception("General failure! Inspect traceback and make the code better!")


if __name__ == "__main__":
    main()
