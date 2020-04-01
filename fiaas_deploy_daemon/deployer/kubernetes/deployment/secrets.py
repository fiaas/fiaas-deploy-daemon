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
import logging

from k8s.models.pod import EnvFromSource, SecretEnvSource, EnvVar, Container, ConfigMapEnvSource, VolumeMount, Volume, \
    EmptyDirVolumeSource, ConfigMapVolumeSource, SecretVolumeSource

from fiaas_deploy_daemon.tools import merge_dicts
from fiaas_deploy_daemon.specs.models import SecretsSpec

LOG = logging.getLogger(__name__)


class Secrets(object):
    def __init__(self, config, kubernetes_secrets, generic_init_secrets):
        self._kubernetes = kubernetes_secrets
        self._generic_init = generic_init_secrets
        self._secrets_service_account_name = config.secrets_service_account_name

    def _legacy_strongbox_secrets_spec(self, app_spec):
        strongbox_params = {
            "AWS_REGION": app_spec.strongbox.aws_region,
            "SECRET_GROUPS": ",".join(app_spec.strongbox.groups),
        }
        strongbox_annotations = {
            "iam.amazonaws.com/role": app_spec.strongbox.iam_role
        }
        return SecretsSpec(type="strongbox",
                           parameters=strongbox_params,
                           annotations=strongbox_annotations,
                           service_account_name=None,
                           automount_service_account_token=False)

    def _legacy_default_init_secret(self):
        return SecretsSpec(type="default",
                           parameters={},
                           annotations={},
                           service_account_name=self._secrets_service_account_name,
                           automount_service_account_token=True)

    def apply(self, deployment, app_spec):
        secret_specs = []
        if not secret_specs:
            if self._generic_init.supports("strongbox") and app_spec.strongbox.enabled:
                secret_specs = [self._legacy_strongbox_secrets_spec(app_spec)]
            elif self._generic_init.supports("default"):
                secret_specs = [self._legacy_default_init_secret()]

        if secret_specs:
            for secret_spec in secret_specs:
                self._generic_init.apply(deployment, app_spec, secret_spec)
        else:
            self._kubernetes.apply(deployment, app_spec)


class KubernetesSecrets(object):
    def apply(self, deployment, app_spec):
        deployment_spec = deployment.spec
        pod_template_spec = deployment_spec.template
        pod_spec = pod_template_spec.spec
        main_container = pod_spec.containers[0]
        env_from = main_container.envFrom

        if app_spec.secrets_in_environment:
            env_from.append(EnvFromSource(secretRef=SecretEnvSource(name=app_spec.name, optional=True)))

        self._apply_mounts(app_spec, main_container)
        self._apply_volumes(app_spec, pod_spec)

    def _apply_volumes(self, app_spec, pod_spec):
        volumes = []
        volumes.extend(self._make_volumes(app_spec))
        volumes.extend(pod_spec.volumes)
        pod_spec.volumes = volumes

    def _apply_mounts(self, app_spec, main_container):
        volume_mounts = []
        volume_mounts.extend(self._make_volume_mounts(app_spec, is_init_container=False))
        volume_mounts.extend(main_container.volumeMounts)
        main_container.volumeMounts = volume_mounts

    def _make_volumes(self, app_spec):
        volumes = [
            Volume(name="{}-secret".format(app_spec.name),
                   secret=SecretVolumeSource(secretName=app_spec.name, optional=True)),
        ]
        return volumes

    def _make_volume_mounts(self, app_spec, is_init_container=False):
        volume_mounts = [
            VolumeMount(name="{}-secret".format(app_spec.name), readOnly=not is_init_container,
                        mountPath="/var/run/secrets/fiaas/"),
        ]
        return volume_mounts


class GenericInitSecrets(KubernetesSecrets):
    SECRETS_INIT_CONTAINER_NAME = "fiaas-secrets-init-container"

    def __init__(self, config):
        self._available_secrets_containers = {}
        if config.strongbox_init_container_image is not None:
            self._available_secrets_containers.setdefault("strongbox", config.strongbox_init_container_image)

        if config.secrets_init_container_image is not None:
            self._available_secrets_containers.setdefault("default", config.secrets_init_container_image)

        self._use_in_memory_emptydirs = config.use_in_memory_emptydirs

    def supports(self, secrets_type):
        return secrets_type in self._available_secrets_containers

    def apply(self, deployment, app_spec, secret_spec):
        deployment_spec = deployment.spec
        pod_template_spec = deployment_spec.template
        pod_spec = pod_template_spec.spec
        main_container = pod_spec.containers[0]
        image = self._available_secrets_containers.get(secret_spec.type)
        if image is None:
            LOG.warning("No init-container registered for secrets with type=%s", secret_spec.type)
            return

        if app_spec.secrets_in_environment:
            LOG.warning("%s is attempting to use 'secrets_in_environment', which is not supported.", app_spec.name)

        self._apply_mounts(app_spec, main_container)

        init_container = self._make_secrets_init_container(app_spec, image, env_vars=secret_spec.parameters)
        pod_spec.initContainers.append(init_container)
        if secret_spec.service_account_name:
            pod_spec.serviceAccountName = secret_spec.service_account_name
        if secret_spec.automount_service_account_token:
            pod_spec.automountServiceAccountToken = True

        pod_metadata = pod_template_spec.metadata
        pod_metadata.annotations = merge_dicts(pod_metadata.annotations, secret_spec.annotations)

        self._apply_volumes(app_spec, pod_spec)

    def _make_volumes(self, app_spec):
        if self._use_in_memory_emptydirs:
            empty_dir_volume_source = EmptyDirVolumeSource(medium="Memory")
        else:
            empty_dir_volume_source = EmptyDirVolumeSource()
        volumes = [
            Volume(name="{}-secret".format(app_spec.name), emptyDir=empty_dir_volume_source),
            Volume(name="{}-config".format(self.SECRETS_INIT_CONTAINER_NAME),
                   configMap=ConfigMapVolumeSource(name=self.SECRETS_INIT_CONTAINER_NAME, optional=True)),
        ]
        return volumes

    def _make_volume_mounts(self, app_spec, is_init_container=False):
        volume_mounts = super(GenericInitSecrets, self)._make_volume_mounts(app_spec, is_init_container)
        if is_init_container:
            init_container_mounts = [
                VolumeMount(name="{}-config".format(self.SECRETS_INIT_CONTAINER_NAME), readOnly=True,
                            mountPath="/var/run/config/{}/".format(self.SECRETS_INIT_CONTAINER_NAME)),
                VolumeMount(name="{}-config".format(app_spec.name), readOnly=True, mountPath="/var/run/config/fiaas/"),
                VolumeMount(name="tmp", readOnly=False, mountPath="/tmp"),
            ]
            volume_mounts.extend(init_container_mounts)
        return volume_mounts

    def _make_secrets_init_container(self, app_spec, image, env_vars=None):
        if env_vars is None:
            env_vars = {}
        env_vars.update({"K8S_DEPLOYMENT": app_spec.name})
        environment = [EnvVar(name=k, value=v) for k, v in env_vars.items()]
        container = Container(name=self.SECRETS_INIT_CONTAINER_NAME,
                              image=image,
                              imagePullPolicy="IfNotPresent",
                              env=environment,
                              envFrom=[
                                  EnvFromSource(configMapRef=ConfigMapEnvSource(name=self.SECRETS_INIT_CONTAINER_NAME,
                                                                                optional=True))
                              ],
                              volumeMounts=self._make_volume_mounts(app_spec, is_init_container=True))
        return container
