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

    def provide_kafka_consumer(self, config):
        host, port = config.resolve_service("kafka_pipeline")
        connect = ",".join("{}:{}".format(host, port) for host in host.split(","))
        return KafkaConsumer(
                "internal.pipeline.deployment",
                bootstrap_servers=connect
        )
