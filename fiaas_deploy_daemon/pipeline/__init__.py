#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import pinject
from kafka import KafkaConsumer

from .consumer import Consumer
from .reporter import Reporter


class PipelineBindings(pinject.BindingSpec):
    def configure(self, bind, require):
        require("session")
        require("config")
        require("deploy_queue")
        bind("reporter", to_class=Reporter)
        bind("consumer", to_class=Consumer)

    def provide_environment(self, config):
        return config.target_cluster

    def provide_kafka_consumer(self, config):
        host, port = config.resolve_service("kafka_pipeline")
        connect = ",".join("{}:{}".format(host, port) for host in host.split(","))
        return KafkaConsumer(
                "internal.pipeline.deployment",
                bootstrap_servers=connect
        )
