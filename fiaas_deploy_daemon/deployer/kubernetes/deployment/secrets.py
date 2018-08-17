#!/usr/bin/env python
# -*- coding: utf-8
from k8s.models.pod import EnvFromSource, SecretEnvSource, EnvVar, Container, ConfigMapEnvSource, VolumeMount, Volume, \
    EmptyDirVolumeSource, ConfigMapVolumeSource, SecretVolumeSource

from fiaas_deploy_daemon.tools import merge_dicts


class Secrets(object):
    SECRETS_INIT_CONTAINER_NAME = "fiaas-secrets-init-container"

    def __init__(self, config):
        self._secrets_init_container_image = config.secrets_init_container_image
        self._secrets_service_account_name = config.secrets_service_account_name
        self._strongbox_init_container_image = config.strongbox_init_container_image

    def apply(self, deployment, app_spec):
        deployment_spec = deployment.spec
        pod_template_spec = deployment_spec.template
        pod_spec = pod_template_spec.spec
        main_container = pod_spec.containers[0]
        env_from = main_container.envFrom
        if app_spec.secrets_in_environment:
            env_from.append(EnvFromSource(secretRef=SecretEnvSource(name=app_spec.name, optional=True)))

        volume_mounts = []
        volume_mounts.extend(self._make_volume_mounts(app_spec, is_init_container=False))
        volume_mounts.extend(main_container.volumeMounts)
        main_container.volumeMounts = volume_mounts

        init_containers = pod_spec.initContainers
        service_account_name = pod_spec.serviceAccountName
        automount_service_account_token = pod_spec.automountServiceAccountToken
        if self._uses_secrets_init_container():
            init_container = self._make_secrets_init_container(app_spec, self._secrets_init_container_image)
            init_containers.append(init_container)
            automount_service_account_token = True
            if self._secrets_service_account_name:
                service_account_name = self._secrets_service_account_name
        elif self._uses_strongbox_init_container(app_spec):
            strongbox_env = {
                "AWS_REGION": app_spec.strongbox.aws_region,
                "SECRET_GROUPS": ",".join(app_spec.strongbox.groups),
            }
            init_container = self._make_secrets_init_container(app_spec, self._strongbox_init_container_image,
                                                               env_vars=strongbox_env)
            init_containers.append(init_container)
        pod_spec.serviceAccountName = service_account_name
        pod_spec.automountServiceAccountToken = automount_service_account_token
        volumes = []
        volumes.extend(self._make_volumes(app_spec))
        volumes.extend(pod_spec.volumes)
        pod_spec.volumes = volumes

        strongbox_annotations = self._make_strongbox_annotations(app_spec) if self._uses_strongbox_init_container(
            app_spec) else {}
        pod_metadata = pod_template_spec.metadata
        pod_metadata.annotations = merge_dicts(pod_metadata.annotations, strongbox_annotations)

    def _make_secrets_init_container(self, app_spec, image, env_vars={}):
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

    def _make_volumes(self, app_spec):
        volumes = []
        if self._uses_secrets_init_container() or self._uses_strongbox_init_container(app_spec):
            volumes.append(Volume(name="{}-secret".format(app_spec.name), emptyDir=EmptyDirVolumeSource()))
            volumes.append(Volume(name="{}-config".format(self.SECRETS_INIT_CONTAINER_NAME),
                                  configMap=ConfigMapVolumeSource(name=self.SECRETS_INIT_CONTAINER_NAME,
                                                                  optional=True)))
        else:
            volumes.append(Volume(name="{}-secret".format(app_spec.name),
                                  secret=SecretVolumeSource(secretName=app_spec.name, optional=True)))
        return volumes

    def _uses_secrets_init_container(self):
        return bool(self._secrets_init_container_image)

    def _uses_strongbox_init_container(self, app_spec):
        return self._strongbox_init_container_image is not None and app_spec.strongbox.enabled

    def _make_volume_mounts(self, app_spec, is_init_container=False):
        volume_mounts = []
        volume_mounts.append(VolumeMount(name="{}-secret".format(app_spec.name),
                                         readOnly=not is_init_container,
                                         mountPath="/var/run/secrets/fiaas/"))
        if is_init_container:
            volume_mounts.append(VolumeMount(name="{}-config".format(self.SECRETS_INIT_CONTAINER_NAME),
                                             readOnly=True,
                                             mountPath="/var/run/config/{}/".format(self.SECRETS_INIT_CONTAINER_NAME)))
            volume_mounts.append(
                VolumeMount(name="{}-config".format(app_spec.name), readOnly=True, mountPath="/var/run/config/fiaas/"))
            volume_mounts.append(VolumeMount(name="tmp", readOnly=False, mountPath="/tmp"))
        return volume_mounts

    @staticmethod
    def _make_strongbox_annotations(app_spec):
        return {"iam.amazonaws.com/role": app_spec.strongbox.iam_role}
