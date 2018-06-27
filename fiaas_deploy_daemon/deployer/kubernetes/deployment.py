#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import logging
import shlex

from k8s.client import NotFound
from k8s.models.common import ObjectMeta
from k8s.models.deployment import Deployment, DeploymentSpec, PodTemplateSpec, LabelSelector
from k8s.models.pod import ContainerPort, EnvVar, HTTPGetAction, TCPSocketAction, ExecAction, HTTPHeader, Container, \
    PodSpec, VolumeMount, Volume, SecretVolumeSource, ResourceRequirements, Probe, ConfigMapEnvSource, \
    ConfigMapVolumeSource, EmptyDirVolumeSource, EnvFromSource, SecretEnvSource, EnvVarSource, SecretKeySelector, \
    Lifecycle, Handler, ResourceFieldSelector, ObjectFieldSelector

from fiaas_deploy_daemon.tools import merge_dicts
from .autoscaler import should_have_autoscaler

LOG = logging.getLogger(__name__)


class DeploymentDeployer(object):
    SECRETS_INIT_CONTAINER_NAME = "fiaas-secrets-init-container"
    DATADOG_CONTAINER_NAME = "fiaas-datadog-container"
    MINIMUM_GRACE_PERIOD = 30

    def __init__(self, config):
        self._fiaas_env = _build_fiaas_env(config)
        self._global_env = config.global_env
        self._secrets_init_container_image = config.secrets_init_container_image
        self._secrets_service_account_name = config.secrets_service_account_name
        self._datadog_container_image = config.datadog_container_image
        self._strongbox_init_container_image = config.strongbox_init_container_image
        self._lifecycle = None
        self._grace_period = self.MINIMUM_GRACE_PERIOD
        if config.pre_stop_delay > 0:
            self._lifecycle = Lifecycle(preStop=Handler(
                _exec=ExecAction(command=["sleep", str(config.pre_stop_delay)])))
            self._grace_period += config.pre_stop_delay

    def deploy(self, app_spec, selector, labels):
        LOG.info("Creating new deployment for %s", app_spec.name)
        deployment_labels = merge_dicts(app_spec.labels.deployment, labels)
        metadata = ObjectMeta(name=app_spec.name, namespace=app_spec.namespace, labels=deployment_labels,
                              annotations=app_spec.annotations.deployment)
        container_ports = [ContainerPort(name=port_spec.name, containerPort=port_spec.target_port) for port_spec in
                           app_spec.ports]
        env = self._make_env(app_spec)
        pull_policy = "IfNotPresent" if (":" in app_spec.image and ":latest" not in app_spec.image) else "Always"

        env_from = [EnvFromSource(configMapRef=ConfigMapEnvSource(name=app_spec.name, optional=True))]
        if app_spec.secrets_in_environment:
            env_from.append(EnvFromSource(secretRef=SecretEnvSource(name=app_spec.name, optional=True)))
        containers = [
            Container(name=app_spec.name,
                      image=app_spec.image,
                      ports=container_ports,
                      env=env,
                      envFrom=env_from,
                      lifecycle=self._lifecycle,
                      livenessProbe=_make_probe(app_spec.health_checks.liveness),
                      readinessProbe=_make_probe(app_spec.health_checks.readiness),
                      imagePullPolicy=pull_policy,
                      volumeMounts=self._make_volume_mounts(app_spec),
                      resources=_make_resource_requirements(app_spec.resources))
        ]
        if app_spec.datadog:
            containers.append(self._create_datadog_container(app_spec))

        automount_service_account_token = app_spec.admin_access
        init_containers = []
        service_account_name = "default"

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

        pod_spec = PodSpec(containers=containers,
                           initContainers=init_containers,
                           volumes=self._make_volumes(app_spec),
                           serviceAccountName=service_account_name,
                           automountServiceAccountToken=automount_service_account_token,
                           terminationGracePeriodSeconds=self._grace_period)

        prometheus_annotations = _make_prometheus_annotations(app_spec) \
            if app_spec.prometheus and app_spec.prometheus.enabled else {}
        strongbox_annotations = _make_strongbox_annotations(app_spec) if self._uses_strongbox_init_container(
            app_spec) else {}
        pod_annotations = merge_dicts(app_spec.annotations.pod, prometheus_annotations, strongbox_annotations)

        pod_labels = merge_dicts(app_spec.labels.pod, _add_status_label(labels))
        pod_metadata = ObjectMeta(name=app_spec.name, namespace=app_spec.namespace, labels=pod_labels,
                                  annotations=pod_annotations)
        pod_template_spec = PodTemplateSpec(metadata=pod_metadata, spec=pod_spec)
        replicas = app_spec.replicas
        # we must avoid that the deployment scales up to app_spec.replicas if autoscaler has set another value
        if should_have_autoscaler(app_spec):
            try:
                deployment = Deployment.get(app_spec.name, app_spec.namespace)
                replicas = deployment.spec.replicas
            except NotFound:
                pass

        spec = DeploymentSpec(replicas=replicas, selector=LabelSelector(matchLabels=selector),
                              template=pod_template_spec, revisionHistoryLimit=5)

        deployment = Deployment.get_or_create(metadata=metadata, spec=spec)
        _clear_pod_init_container_annotations(deployment)
        deployment.save()

    def _create_datadog_container(self, app_spec):
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
            ]
        )

    def delete(self, app_spec):
        LOG.info("Deleting deployment for %s", app_spec.name)
        try:
            body = {"kind": "DeleteOptions", "apiVersion": "v1", "propagationPolicy": "Foreground"}
            Deployment.delete(app_spec.name, app_spec.namespace, body=body)
        except NotFound:
            pass

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
        volumes.append(Volume(name="{}-config".format(app_spec.name),
                              configMap=ConfigMapVolumeSource(name=app_spec.name, optional=True)))
        volumes.append(Volume(name="tmp", emptyDir=EmptyDirVolumeSource()))
        return volumes

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

    def _make_env(self, app_spec):
        constants = self._fiaas_env.copy()
        constants["ARTIFACT_NAME"] = app_spec.name
        constants["IMAGE"] = app_spec.image
        constants["VERSION"] = app_spec.version
        env = [EnvVar(name=name, value=value) for name, value in constants.iteritems()]

        # For backward compatability. https://github.schibsted.io/finn/fiaas-deploy-daemon/pull/34
        global_env = []
        for name, value in self._global_env.iteritems():
            if "FIAAS_{}".format(name) not in constants and name not in constants:
                global_env.extend([EnvVar(name=name, value=value), EnvVar(name="FIAAS_{}".format(name), value=value)])
            else:
                LOG.warn("Reserved environment-variable: {} declared as global. Ignoring and continuing".format(name))
        env.extend(global_env)

        env.extend([
            EnvVar(name="FIAAS_REQUESTS_CPU", valueFrom=EnvVarSource(
                resourceFieldRef=ResourceFieldSelector(containerName=app_spec.name, resource="requests.cpu",
                                                       divisor=1))),
            EnvVar(name="FIAAS_REQUESTS_MEMORY", valueFrom=EnvVarSource(
                resourceFieldRef=ResourceFieldSelector(containerName=app_spec.name, resource="requests.memory",
                                                       divisor=1))),
            EnvVar(name="FIAAS_LIMITS_CPU", valueFrom=EnvVarSource(
                resourceFieldRef=ResourceFieldSelector(containerName=app_spec.name, resource="limits.cpu", divisor=1))),
            EnvVar(name="FIAAS_LIMITS_MEMORY", valueFrom=EnvVarSource(
                resourceFieldRef=ResourceFieldSelector(containerName=app_spec.name, resource="limits.memory",
                                                       divisor=1))),
            EnvVar(name="FIAAS_NAMESPACE", valueFrom=EnvVarSource(
                fieldRef=ObjectFieldSelector(fieldPath="metadata.namespace"))),
            EnvVar(name="FIAAS_POD_NAME", valueFrom=EnvVarSource(
                fieldRef=ObjectFieldSelector(fieldPath="metadata.name"))),
        ])

        if app_spec.datadog:
            env.append(EnvVar(name="STATSD_HOST", value="localhost"))
            env.append(EnvVar(name="STATSD_PORT", value="8125"))
        env.sort(key=lambda x: x.name)
        return env

    def _uses_secrets_init_container(self):
        return bool(self._secrets_init_container_image)

    def _uses_strongbox_init_container(self, app_spec):
        return self._strongbox_init_container_image is not None and app_spec.strongbox.enabled


def _clear_pod_init_container_annotations(deployment):
    """Kubernetes 1.5 implemented init-containers using annotations, and in order to preserve backwards compatibility in
    1.6 and 1.7, those annotations take precedence over the actual initContainer element in the spec object. In order to
    ensure that any changes we make take effect, we clear the annotations.
    """
    keys_to_clear = set()
    try:
        if deployment.spec.template.metadata.annotations:
            for key, _ in deployment.spec.template.metadata.annotations.items():
                if key.endswith("kubernetes.io/init-containers"):
                    keys_to_clear.add(key)
            for key in keys_to_clear:
                del deployment.spec.template.metadata.annotations[key]
    except AttributeError:
        pass


def _add_status_label(labels):
    copy = labels.copy()
    copy.update({
        "fiaas/status": "active"
    })
    return copy


def _make_prometheus_annotations(app_spec):
    lookup = {p.name: p.target_port for p in app_spec.ports}
    prometheus_spec = app_spec.prometheus
    try:
        port = int(prometheus_spec.port)
    except ValueError:
        try:
            port = lookup[prometheus_spec.port]
        except KeyError:
            LOG.error("Invalid prometheus configuration for %s", app_spec.name)
            return {}
    return {
        "prometheus.io/scrape": str(prometheus_spec.enabled).lower(),
        "prometheus.io/port": str(port),
        "prometheus.io/path": prometheus_spec.path
    }


def _make_strongbox_annotations(app_spec):
    return {"iam.amazonaws.com/role": app_spec.strongbox.iam_role}


def _make_resource_requirements(resources_spec):
    def as_dict(resource_requirement_spec):
        return {"cpu": resource_requirement_spec.cpu, "memory": resource_requirement_spec.memory}

    return ResourceRequirements(limits=as_dict(resources_spec.limits), requests=as_dict(resources_spec.requests))


def _make_probe(check_spec):
    probe = Probe(initialDelaySeconds=check_spec.initial_delay_seconds, timeoutSeconds=check_spec.timeout_seconds,
                  successThreshold=check_spec.success_threshold, periodSeconds=check_spec.period_seconds)
    if check_spec.http:
        probe.httpGet = HTTPGetAction(path=check_spec.http.path, port=check_spec.http.port,
                                      httpHeaders=[HTTPHeader(name=name, value=value)
                                                   for name, value in check_spec.http.http_headers.items()])
    elif check_spec.tcp:
        probe.tcpSocket = TCPSocketAction(port=check_spec.tcp.port)
    elif check_spec.execute:
        probe._exec = ExecAction(command=shlex.split(check_spec.execute.command))
    else:
        raise RuntimeError("AppSpec must have exactly one health check, none was defined.")

    return probe


def _build_fiaas_env(config):
    env = {
        "FIAAS_INFRASTRUCTURE": config.infrastructure,
        "LOG_STDOUT": "true",
        "LOG_FORMAT": config.log_format,
        "CONSTRETTO_TAGS": "kubernetes",
    }
    if config.environment:
        env.update({
            "FINN_ENV": config.environment,  # DEPRECATED. Remove in the future.
            "FIAAS_ENVIRONMENT": config.environment,
            "CONSTRETTO_TAGS": ",".join(("kubernetes-{}".format(config.environment), "kubernetes", config.environment)),
        })
    return env
