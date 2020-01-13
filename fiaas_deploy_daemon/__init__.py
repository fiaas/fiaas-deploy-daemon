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
from .fake_consumer import FakeConsumerBindings
from .lifecycle import Lifecycle
from .logsetup import init_logging
from .pipeline import PipelineBindings
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
    def __init__(self, deployer, consumer, scheduler, crd_watcher, usage_reporter):
        pass

    def is_healthy(self):
        return all((
            self._deployer.is_alive(),
            self._consumer.is_alive(),
            self._scheduler.is_alive(),
            self._crd_watcher.is_alive(),
            self._usage_reporter.is_alive(),
        ))


class Main(object):
    @pinject.copy_args_to_internal_fields
    def __init__(self, deployer, consumer, scheduler, webapp, config, crd_watcher, usage_reporter):
        pass

    def run(self):
        self._deployer.start()
        self._consumer.start()
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


def main():
    cfg = Configuration()
    init_logging(cfg)
    init_k8s_client(cfg)
    log = logging.getLogger(__name__)
    signal.signal(signal.SIGUSR2, thread_dump_logger(log))
    try:
        log.info("fiaas-deploy-daemon starting with configuration {!r}".format(cfg))
        binding_specs = [
            MainBindings(cfg),
            DeployerBindings(),
            K8sAdapterBindings(),
            WebBindings(),
            SpecBindings(),
            PipelineBindings() if not cfg.disable_pipeline_consumer and cfg.has_service("kafka_pipeline") else FakeConsumerBindings(),
            CustomResourceDefinitionBindings() if cfg.enable_crd_support else DisabledCustomResourceDefinitionBindings(),
            UsageReportingBindings(),
        ]
        obj_graph = pinject.new_object_graph(modules=None, binding_specs=binding_specs)
        obj_graph.provide(Main).run()
    except BaseException:
        log.exception("General failure! Inspect traceback and make the code better!")


if __name__ == "__main__":
    main()
