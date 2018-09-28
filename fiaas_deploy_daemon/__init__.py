#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import logging
from Queue import Queue

import pinject
import requests
from k8s import config as k8s_config

from .config import Configuration
from .crd import CustomResourceDefinitionBindings, DisabledCustomResourceDefinitionBindings
from .deployer import DeployerBindings
from .deployer.kubernetes import K8sAdapterBindings
from .fake_consumer import FakeConsumerBindings
from .logsetup import init_logging
from .pipeline import PipelineBindings
from .secrets import resolve_secrets
from .specs import SpecBindings
from .tpr import ThirdPartyResourceBindings, DisabledThirdPartyResourceBindings
from .tracking import TrackingBindings
from .web import WebBindings


class MainBindings(pinject.BindingSpec):
    def __init__(self, config):
        self._config = config
        self._deploy_queue = Queue()

    def configure(self, bind):
        bind("config", to_instance=self._config)
        bind("deploy_queue", to_instance=self._deploy_queue)
        bind("health_check", to_class=HealthCheck)

    def provide_session(self, config):
        session = requests.Session()
        if config.proxy:
            session.proxies = {scheme: config.proxy for scheme in (
                "http",
                "https"
            )}
        return session

    def provide_secrets(self, config):
        return resolve_secrets(config.secrets_directory)


class HealthCheck(object):
    @pinject.copy_args_to_internal_fields
    def __init__(self, deployer, consumer, scheduler, tpr_watcher, crd_watcher, usage_reporter):
        pass

    def is_healthy(self):
        return all((
            self._deployer.is_alive(),
            self._consumer.is_alive(),
            self._scheduler.is_alive(),
            self._tpr_watcher.is_alive(),
            self._crd_watcher.is_alive(),
            self._usage_reporter.is_alive(),
        ))


class Main(object):
    @pinject.copy_args_to_internal_fields
    def __init__(self, deployer, consumer, scheduler, webapp, config, tpr_watcher, crd_watcher, usage_reporter):
        pass

    def run(self):
        self._deployer.start()
        self._consumer.start()
        self._scheduler.start()
        self._tpr_watcher.start()
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


def main():
    cfg = Configuration()
    init_logging(cfg)
    init_k8s_client(cfg)
    log = logging.getLogger(__name__)
    try:
        log.info("fiaas-deploy-daemon starting with configuration {!r}".format(cfg))
        binding_specs = [
            MainBindings(cfg),
            DeployerBindings(),
            K8sAdapterBindings(),
            WebBindings(),
            SpecBindings(),
            PipelineBindings() if cfg.has_service("kafka_pipeline") else FakeConsumerBindings(),
            ThirdPartyResourceBindings() if cfg.enable_tpr_support else DisabledThirdPartyResourceBindings(),
            CustomResourceDefinitionBindings() if cfg.enable_crd_support else DisabledCustomResourceDefinitionBindings(),
            TrackingBindings(),
        ]
        obj_graph = pinject.new_object_graph(modules=None, binding_specs=binding_specs)
        obj_graph.provide(Main).run()
    except BaseException:
        log.exception("General failure! Inspect traceback and make the code better!")


if __name__ == "__main__":
    main()
