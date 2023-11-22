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
from k8s.models.pod import (
    ResourceRequirements,
    Container,
    EnvVar,
    EnvVarSource,
    ExecAction,
    Handler,
    Lifecycle,
    SecretKeySelector,
)
from k8s.models.deployment import Deployment


class DataDog(object):
    DATADOG_CONTAINER_NAME = "fiaas-datadog-container"

    def __init__(self, config):
        self._datadog_container_image = config.datadog_container_image
        self._datadog_container_memory = config.datadog_container_memory
        self._datadog_global_tags = config.datadog_global_tags
        self._datadog_activate_sleep = config.datadog_activate_sleep

    def apply(self, deployment: Deployment, app_spec, besteffort_qos_is_required, pre_stop_delay):
        if app_spec.datadog.enabled:
            containers = deployment.spec.template.spec.containers
            main_container = containers[0]
            containers.append(self._create_datadog_container(app_spec, besteffort_qos_is_required, pre_stop_delay))
            # TODO: Bug in k8s library allows us to mutate the default value here, so we need to take a copy
            env = list(main_container.env)
            env.extend(self._get_env_vars())
            env.sort(key=lambda x: x.name)
            main_container.env = env

    def _create_datadog_container(self, app_spec, besteffort_qos_is_required, pre_stop_delay):
        if besteffort_qos_is_required:
            resource_requirements = ResourceRequirements()
        else:
            resource_requirements = ResourceRequirements(
                limits={"cpu": "400m", "memory": self._datadog_container_memory},
                requests={"cpu": "200m", "memory": self._datadog_container_memory},
            )

        tags = {}
        if self._datadog_global_tags:
            tags.update(self._datadog_global_tags)

        tags.update(app_spec.datadog.tags)
        tags["app"] = app_spec.name
        tags["k8s_namespace"] = app_spec.namespace
        # Use an alphabetical order based on keys to ensure that the
        # output is predictable
        dd_tags = ",".join("{}:{}".format(k, tags[k]) for k in sorted(tags))

        image_pull_policy = "IfNotPresent"
        if ":" not in self._datadog_container_image or ":latest" in self._datadog_container_image:
            image_pull_policy = "Always"

        lifecycle = None
        if pre_stop_delay > 0 and self._datadog_activate_sleep:
            lifecycle = Lifecycle(preStop=Handler(_exec=ExecAction(command=["sleep", str(pre_stop_delay)])))

        return Container(
            name=self.DATADOG_CONTAINER_NAME,
            image=self._datadog_container_image,
            imagePullPolicy=image_pull_policy,
            env=[
                EnvVar(name="DD_TAGS", value=dd_tags),
                EnvVar(
                    name="DD_API_KEY",
                    valueFrom=EnvVarSource(secretKeyRef=SecretKeySelector(name="datadog", key="apikey")),
                ),
                EnvVar(name="NON_LOCAL_TRAFFIC", value="false"),
                EnvVar(name="DD_LOGS_STDOUT", value="yes"),
                EnvVar(name="DD_EXPVAR_PORT", value="42622"),
                EnvVar(name="DD_CMD_PORT", value="42623"),
            ],
            lifecycle=lifecycle,
            resources=resource_requirements,
        )

    @staticmethod
    def _get_env_vars():
        return (EnvVar(name="STATSD_HOST", value="localhost"), EnvVar(name="STATSD_PORT", value="8125"))
