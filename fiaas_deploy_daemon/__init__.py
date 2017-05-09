#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import logging
from Queue import Queue

import pinject
import requests

from .config import Configuration
from .deployer import DeployerBindings
from .deployer.kubernetes import K8sAdapterBindings
from .fake_consumer import FakeConsumerBindings
from .logsetup import init_logging
from .pipeline import PipelineBindings
from .specs import SpecBindings
from .tpr import ThirdPartyResourceBindings, DisabledThirdPartyResourceBindings
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


class HealthCheck(object):
    @pinject.copy_args_to_internal_fields
    def __init__(self, deployer, consumer, scheduler, tpr_watcher):
        pass

    def is_healthy(self):
        return (self._deployer.is_alive() and
                self._consumer.is_alive() and
                self._scheduler.is_alive() and
                self._consumer.is_recieving_messages(),
                self._tpr_watcher.is_alive())


class Main(object):
    @pinject.copy_args_to_internal_fields
    def __init__(self, deployer, consumer, scheduler, webapp, config, tpr_watcher):
        pass

    def run(self):
        self._deployer.start()
        self._consumer.start()
        self._scheduler.start()
        self._tpr_watcher.start()
        # Run web-app in main thread
        self._webapp.run("0.0.0.0", self._config.port)


def main():
    cfg = Configuration()
    init_logging(cfg)
    log = logging.getLogger(__name__)
    try:
        log.info("fiaas-deploy-daemon starting with configuration {!r}".format(cfg))
        binding_specs = [
            MainBindings(cfg),
            DeployerBindings(),
            K8sAdapterBindings(),
            WebBindings(),
            SpecBindings()
        ]
        if cfg.has_service("kafka_pipeline"):
            binding_specs.append(PipelineBindings())
        else:
            binding_specs.append(FakeConsumerBindings())
        binding_specs.append(ThirdPartyResourceBindings() if cfg.enable_tpr_support
                             else DisabledThirdPartyResourceBindings())
        obj_graph = pinject.new_object_graph(modules=None, binding_specs=binding_specs)
        obj_graph.provide(Main).run()
    except:
        log.exception("General failure! Inspect traceback and make the code better!")


if __name__ == "__main__":
    main()
