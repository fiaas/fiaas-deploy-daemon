#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import logging

from Queue import Queue

import pinject
import requests

from .. import init_k8s_client
from ..config import Configuration
from ..deployer import DeployerBindings
from ..deployer.kubernetes import K8sAdapterBindings
from ..logsetup import init_logging
from ..specs import SpecBindings
from .bootstrapper import Bootstrapper


class MainBindings(pinject.BindingSpec):
    def __init__(self, config):
        self._config = config
        self._deploy_queue = Queue()

    def configure(self, bind):
        bind("config", to_instance=self._config)
        bind("deploy_queue", to_instance=self._deploy_queue)
        bind("bootstrapper", to_class=Bootstrapper)

    def provide_session(self, config):
        session = requests.Session()
        if config.proxy:
            session.proxies = {scheme: config.proxy for scheme in (
                "http",
                "https"
            )}
        return session


class Main(object):
    @pinject.copy_args_to_internal_fields
    def __init__(self, deployer, scheduler, config):
        pass

    def run(self):
        self._deployer.start()
        self._scheduler.start()
        self._bootstrapper.run()  # run bootstrapper on main thread


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
            SpecBindings(),
        ]
        obj_graph = pinject.new_object_graph(modules=None, binding_specs=binding_specs)
        obj_graph.provide(Main).run()
    except BaseException:
        log.exception("General failure! Inspect traceback and make the code better!")


if __name__ == '__main__':
    main()
