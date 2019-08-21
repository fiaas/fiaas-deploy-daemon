#!/usr/bin/env python
# -*- coding: utf-8
from k8s.models.pod import ResourceRequirements, Container, EnvVar, EnvVarSource, SecretKeySelector


class DataDog(object):
    DATADOG_CONTAINER_NAME = "fiaas-datadog-container"

    def __init__(self, config):
        self._datadog_container_image = config.datadog_container_image

    def apply(self, deployment, app_spec, besteffort_qos_is_required):
        if app_spec.datadog.enabled:
            containers = deployment.spec.template.spec.containers
            main_container = containers[0]
            containers.append(self._create_datadog_container(app_spec, besteffort_qos_is_required))
            # TODO: Bug in k8s library allows us to mutate the default value here, so we need to take a copy
            env = list(main_container.env)
            env.extend(self._get_env_vars())
            env.sort(key=lambda x: x.name)
            main_container.env = env

    def _create_datadog_container(self, app_spec, besteffort_qos_is_required):
        if besteffort_qos_is_required:
            resource_requirements = ResourceRequirements()
        else:
            resource_requirements = ResourceRequirements(limits={"cpu": "400m", "memory": "2Gi"},
                                                         requests={"cpu": "200m", "memory": "2Gi"})

        tags = app_spec.datadog.tags
        tags["app"] = app_spec.name
        tags["k8s_namespace"] = app_spec.namespace
        # Use an alphabetical order based on keys to ensure that the
        # output is predictable
        dd_tags = ",".join("{}:{}".format(k, tags[k]) for k in sorted(tags))

        return Container(
            name=self.DATADOG_CONTAINER_NAME,
            image=self._datadog_container_image,
            imagePullPolicy="IfNotPresent",
            env=[
                EnvVar(name="DD_TAGS", value=dd_tags),
                EnvVar(name="DD_API_KEY",
                       valueFrom=EnvVarSource(secretKeyRef=SecretKeySelector(name="datadog", key="apikey"))),
                EnvVar(name="NON_LOCAL_TRAFFIC", value="false"),
                EnvVar(name="DD_LOGS_STDOUT", value="yes"),
                EnvVar(name="DD_EXPVAR_PORT", value="42622"),
                EnvVar(name="DD_CMD_PORT", value="42623"),
            ],
            resources=resource_requirements
        )

    @staticmethod
    def _get_env_vars():
        return (
            EnvVar(name="STATSD_HOST", value="localhost"),
            EnvVar(name="STATSD_PORT", value="8125")
        )
