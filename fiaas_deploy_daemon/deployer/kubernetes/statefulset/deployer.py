#!/usr/bin/env python
# -*- coding: utf-8

# Copyright 2017-2024 The FIAAS Authors
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

import logging

from fiaas_deploy_daemon.config import Configuration
from fiaas_deploy_daemon.retry import retry_on_upsert_conflict
from fiaas_deploy_daemon.tools import merge_dicts

from k8s.client import NotFound
from k8s.models.common import ObjectMeta
from k8s.models.deployment import Deployment, LabelSelector

from k8s.models.pod import (
    ConfigMapEnvSource,
    ConfigMapVolumeSource,
    Container,
    ContainerPort,
    EmptyDirVolumeSource,
    EnvFromSource,
    EnvVar,
    EnvVarSource,
    ExecAction,
    Handler,
    Lifecycle,
    ObjectFieldSelector,
    PodDNSConfig,
    PodSpec,
    PodTemplateSpec,
    ResourceFieldSelector,
    ResourceRequirements,
    Volume,
    VolumeMount,
)

from fiaas_deploy_daemon.deployer.kubernetes.deployment.datadog import DataDog
from fiaas_deploy_daemon.deployer.kubernetes.deployment.prometheus import Prometheus
from fiaas_deploy_daemon.deployer.kubernetes.deployment.secrets import Secrets
from fiaas_deploy_daemon.deployer.kubernetes.owner_references import OwnerReferences
from fiaas_deploy_daemon.extension_hook_caller import ExtensionHookCaller
from fiaas_deploy_daemon.deployer.kubernetes.deployment.deployer import (
    _build_fiaas_env,
    _build_global_env,
    _add_status_label,
    _make_probe,
    _make_resource_requirements,
)
from .k8s_models import (
    PersistentVolumeClaim,
    PersistentVolumeClaimSpec,
    StatefulSet,
    StatefulSetSpec,
    StatefulSetUpdateStrategy,
    RollingUpdateStatefulSetStrategy,
)

LOG = logging.getLogger(__name__)


class StatefulSetDeployer(object):
    MINIMUM_GRACE_PERIOD = 30
    DATADOG_PRE_STOP_DELAY = 5

    def __init__(
        self,
        config: Configuration,
        datadog,
        prometheus,
        deployment_secrets,
        owner_references,
        extension_hook,
    ):
        self._datadog: DataDog = datadog
        self._prometheus: Prometheus = prometheus
        self._secrets: Secrets = deployment_secrets
        self._owner_references: OwnerReferences = owner_references
        self._extension_hook: ExtensionHookCaller = extension_hook
        self._pre_stop_delay = config.pre_stop_delay
        self._legacy_fiaas_env = _build_fiaas_env(config)
        self._global_env = _build_global_env(config.global_env)
        self._lifecycle: Lifecycle | None = None
        self._grace_period = self.MINIMUM_GRACE_PERIOD
        self._use_in_memory_emptydirs = config.use_in_memory_emptydirs
        if self._pre_stop_delay > 0:
            self._lifecycle = Lifecycle(preStop=Handler(_exec=ExecAction(command=["sleep", str(self._pre_stop_delay)])))
            self._grace_period += self._pre_stop_delay
        self._disable_deprecated_managed_env_vars = config.disable_deprecated_managed_env_vars
        self._enable_service_links = False if config.enable_service_links is False else None
        self._dns_search_domains = config.dns_search_domains
        self._enable_service_account_per_app = config.enable_service_account_per_app

    @retry_on_upsert_conflict(max_value_seconds=5, max_tries=5)
    def deploy(self, app_spec, selector, labels, besteffort_qos_is_required):
        if not app_spec.statefulset.enabled:
            self._delete(app_spec)
            return

        LOG.info("Creating new statefulset for %s", app_spec.name)

        try:
            Deployment.delete(app_spec.name, app_spec.namespace)
        except NotFound:
            pass

        metadata = ObjectMeta(
            name=app_spec.name,
            namespace=app_spec.namespace,
            labels=merge_dicts(app_spec.labels.deployment, labels),
            annotations=app_spec.annotations.deployment,
        )

        container_ports = [
            ContainerPort(name=port_spec.name, containerPort=port_spec.target_port) for port_spec in app_spec.ports
        ]
        env = self._make_env(app_spec)
        pull_policy = "IfNotPresent" if (":" in app_spec.image and ":latest" not in app_spec.image) else "Always"
        env_from = [EnvFromSource(configMapRef=ConfigMapEnvSource(name=app_spec.name, optional=True))]
        containers = [
            Container(
                name=app_spec.name,
                image=app_spec.image,
                ports=container_ports,
                env=env,
                envFrom=env_from,
                lifecycle=self._lifecycle,
                livenessProbe=_make_probe(app_spec.health_checks.liveness),
                readinessProbe=_make_probe(app_spec.health_checks.readiness),
                imagePullPolicy=pull_policy,
                volumeMounts=self._make_volume_mounts(app_spec),
                resources=_make_resource_requirements(app_spec.resources),
            )
        ]

        dns_config = None
        if self._dns_search_domains:
            dns_config = PodDNSConfig(searches=self._dns_search_domains)

        service_account_name = app_spec.name if self._enable_service_account_per_app else "default"

        pod_spec = PodSpec(
            containers=containers,
            initContainers=[],
            volumes=self._make_volumes(app_spec),
            serviceAccountName=service_account_name,
            automountServiceAccountToken=app_spec.admin_access,
            terminationGracePeriodSeconds=self._grace_period,
            enableServiceLinks=self._enable_service_links,
            dnsConfig=dns_config,
        )

        pod_metadata = ObjectMeta(
            name=app_spec.name,
            namespace=app_spec.namespace,
            labels=merge_dicts(app_spec.labels.pod, _add_status_label(labels)),
            annotations=app_spec.annotations.pod,
        )
        pod_template_spec = PodTemplateSpec(metadata=pod_metadata, spec=pod_spec)

        spec = StatefulSetSpec(
            serviceName=app_spec.statefulset.service_name or app_spec.name,
            replicas=app_spec.autoscaler.min_replicas,
            selector=LabelSelector(matchLabels=selector),
            template=pod_template_spec,
            updateStrategy=self._make_update_strategy(app_spec.statefulset.update_strategy),
            podManagementPolicy=app_spec.statefulset.pod_management_policy,
            volumeClaimTemplates=self._make_volume_claim_templates(app_spec),
        )

        statefulset = StatefulSet.get_or_create(metadata=metadata, spec=spec)
        self._datadog.apply(
            statefulset,
            app_spec,
            besteffort_qos_is_required,
            self._pre_stop_delay + self.DATADOG_PRE_STOP_DELAY,
        )
        self._prometheus.apply(statefulset, app_spec)
        self._secrets.apply(statefulset, app_spec)
        self._owner_references.apply(statefulset, app_spec)
        self._extension_hook.apply(statefulset, app_spec)
        statefulset.save()

    def _delete(self, app_spec):
        try:
            StatefulSet.delete(app_spec.name, app_spec.namespace)
        except NotFound:
            pass

    def _make_volumes(self, app_spec):
        volumes = [
            Volume(
                name="{}-config".format(app_spec.name),
                configMap=ConfigMapVolumeSource(name=app_spec.name, optional=True),
            )
        ]
        empty_dir_volume_source = EmptyDirVolumeSource(medium="Memory") if self._use_in_memory_emptydirs else EmptyDirVolumeSource()
        volumes.append(Volume(name="tmp", emptyDir=empty_dir_volume_source))
        return volumes

    def _make_volume_mounts(self, app_spec):
        mounts = [
            VolumeMount(name="{}-config".format(app_spec.name), readOnly=True, mountPath="/var/run/config/fiaas/"),
            VolumeMount(name="tmp", readOnly=False, mountPath="/tmp"),
        ]
        for claim in app_spec.statefulset.volume_claims:
            mounts.append(VolumeMount(name=claim.name, readOnly=False, mountPath=claim.mount_path))
        return mounts

    def _make_volume_claim_templates(self, app_spec):
        templates = []
        for claim in app_spec.statefulset.volume_claims:
            metadata = ObjectMeta(name=claim.name, annotations=claim.annotations)
            limits = claim.resources.limits or None
            resources = ResourceRequirements(requests=claim.resources.requests, limits=limits)
            pvc_spec = PersistentVolumeClaimSpec(
                accessModes=claim.access_modes,
                resources=resources,
                storageClassName=claim.storage_class_name,
            )
            templates.append(PersistentVolumeClaim(metadata=metadata, spec=pvc_spec))
        return templates

    @staticmethod
    def _make_update_strategy(strategy_spec):
        rolling_update = None
        if strategy_spec.type == "RollingUpdate" and strategy_spec.rolling_update_partition is not None:
            rolling_update = RollingUpdateStatefulSetStrategy(partition=strategy_spec.rolling_update_partition)
        return StatefulSetUpdateStrategy(type=strategy_spec.type, rollingUpdate=rolling_update)

    def _make_env(self, app_spec):
        fiaas_managed_env = {
            "FIAAS_ARTIFACT_NAME": app_spec.name,
            "FIAAS_IMAGE": app_spec.image,
            "FIAAS_VERSION": app_spec.version,
        }
        if not self._disable_deprecated_managed_env_vars:
            fiaas_managed_env.update(
                {
                    "ARTIFACT_NAME": app_spec.name,
                    "IMAGE": app_spec.image,
                    "VERSION": app_spec.version,
                }
            )

        static_env = merge_dicts(self._legacy_fiaas_env, self._global_env, fiaas_managed_env)
        env = [EnvVar(name=name, value=value) for name, value in list(static_env.items())]
        env.extend(
            [
                EnvVar(
                    name="FIAAS_REQUESTS_CPU",
                    valueFrom=EnvVarSource(resourceFieldRef=ResourceFieldSelector(resource="requests.cpu")),
                ),
                EnvVar(
                    name="FIAAS_REQUESTS_MEMORY",
                    valueFrom=EnvVarSource(resourceFieldRef=ResourceFieldSelector(resource="requests.memory")),
                ),
                EnvVar(
                    name="FIAAS_LIMITS_CPU",
                    valueFrom=EnvVarSource(resourceFieldRef=ResourceFieldSelector(resource="limits.cpu")),
                ),
                EnvVar(
                    name="FIAAS_LIMITS_MEMORY",
                    valueFrom=EnvVarSource(resourceFieldRef=ResourceFieldSelector(resource="limits.memory")),
                ),
                EnvVar(
                    name="FIAAS_NAMESPACE",
                    valueFrom=EnvVarSource(fieldRef=ObjectFieldSelector(fieldPath="metadata.namespace")),
                ),
                EnvVar(
                    name="FIAAS_POD_NAME",
                    valueFrom=EnvVarSource(fieldRef=ObjectFieldSelector(fieldPath="metadata.name")),
                ),
            ]
        )
        env.sort(key=lambda item: item.name)
        return env
