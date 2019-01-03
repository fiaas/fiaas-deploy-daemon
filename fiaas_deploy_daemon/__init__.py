#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import logging
from Queue import Queue

import pinject
import requests
from gevent import monkey
from gevent.pywsgi import WSGIServer, LoggingLogAdapter
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
from .tools import log_request_response
from .tpr import ThirdPartyResourceBindings, DisabledThirdPartyResourceBindings
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
        log = LoggingLogAdapter(self._webapp.request_logger, logging.DEBUG)
        error_log = LoggingLogAdapter(self._webapp.request_logger, logging.ERROR)
        http_server = WSGIServer(("", self._config.port), self._webapp, log=log, error_log=error_log)
        http_server.serve_forever()


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
    _monkeypatch()

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
            UsageReportingBindings(),
        ]
        obj_graph = pinject.new_object_graph(modules=None, binding_specs=binding_specs)
        obj_graph.provide(Main).run()
    except BaseException:
        log.exception("General failure! Inspect traceback and make the code better!")


def _monkeypatch():
    """Add gevent monkey patches to enable the use of the non-blocking WSGIServer

    The late patching is because we want to avoid patching when running in bootstrap mode, and that would require
    some bigger refactoring since bootstrap imports the root package.

    The reason the documentation recommends to do patching before imports is to avoid the case where imported code
    makes aliases for the attributes that will be patched (and end up continuing to use the unpatched attribute).
    Since we reduce our patching to just four things it's easier to reason about this risk (ie. I don't think it's a
    problem for us). Also, patch_all made some things fail, such as `select` and something with handling of requests in
    Flask (read timeout).

    At this point we should still be single-threaded, so it's reasonably safe.
    """
    monkey.patch_socket()
    monkey.patch_ssl()
    monkey.patch_time()
    monkey.patch_queue()


if __name__ == "__main__":
    main()
