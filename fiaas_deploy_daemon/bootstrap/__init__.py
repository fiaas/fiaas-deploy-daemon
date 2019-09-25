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
import sys
from Queue import Queue

import pinject
import requests

from .bootstrapper import Bootstrapper
from .. import init_k8s_client
from ..config import Configuration
from ..deployer import DeployerBindings
from ..deployer.kubernetes import K8sAdapterBindings
from ..lifecycle import Lifecycle
from ..logsetup import init_logging
from ..specs import SpecBindings


class MainBindings(pinject.BindingSpec):
    def __init__(self, config):
        self._config = config
        self._deploy_queue = Queue()

    def configure(self, bind):
        bind("config", to_instance=self._config)
        bind("deploy_queue", to_instance=self._deploy_queue)
        bind("bootstrapper", to_class=Bootstrapper)
        bind("lifecycle", to_class=Lifecycle)

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
    def __init__(self, deployer, scheduler, config, bootstrapper):
        pass

    def run(self):
        self._deployer.start()
        self._scheduler.start()
        if not self._bootstrapper.run():
            sys.exit(1)


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
        sys.exit(1)


if __name__ == '__main__':
    main()
