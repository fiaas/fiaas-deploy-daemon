#!/usr/bin/env python
# -*- coding: utf-8
from k8s.models.pod import ResourceRequirements, Container, EnvVar, EnvVarSource, SecretKeySelector


class DataDog(object):
    DATADOG_CONTAINER_NAME = "fiaas-datadog-container"

    def __init__(self, config):
        self._datadog_container_image = config.datadog_container_image

    def create_datadog_container(self, app_spec, besteffort_qos_is_required):
        if besteffort_qos_is_required:
            resource_requirements = ResourceRequirements()
        else:
            resource_requirements = ResourceRequirements(limits={"cpu": "400m", "memory": "2Gi"},
                                                         requests={"cpu": "200m", "memory": "2Gi"})
        return Container(
            name=self.DATADOG_CONTAINER_NAME,
            image=self._datadog_container_image,
            imagePullPolicy="IfNotPresent",
            env=[
                EnvVar(name="DD_TAGS", value="app:{},k8s_namespace:{}".format(app_spec.name, app_spec.namespace)),
                EnvVar(name="API_KEY",
                       valueFrom=EnvVarSource(secretKeyRef=SecretKeySelector(name="datadog", key="apikey"))),
                EnvVar(name="NON_LOCAL_TRAFFIC", value="false"),
                EnvVar(name="DD_LOGS_STDOUT", value="yes"),
            ],
            resources=resource_requirements
        )

    @staticmethod
    def get_env_vars():
        return (
            EnvVar(name="STATSD_HOST", value="localhost"),
            EnvVar(name="STATSD_PORT", value="8125")
        )
