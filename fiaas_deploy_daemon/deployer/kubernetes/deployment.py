#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import logging
import shlex

from k8s.client import NotFound
from k8s.models.common import ObjectMeta
from k8s.models.deployment import Deployment, DeploymentSpec, PodTemplateSpec, LabelSelector
from k8s.models.pod import ContainerPort, EnvVar, HTTPGetAction, TCPSocketAction, ExecAction, HTTPHeader, Container, \
    PodSpec, VolumeMount, Volume, SecretVolumeSource, ResourceRequirements, Probe, EnvVarSource, ConfigMapKeySelector, \
    ConfigMapVolumeSource
from .autoscaler import should_have_autoscaler

LOG = logging.getLogger(__name__)


class DeploymentDeployer(object):
    def __init__(self, config):
        self._fiaas_env = {
            "FINN_ENV": config.environment,  # DEPRECATED. Remove in the future.
            "FIAAS_INFRASTRUCTURE": config.infrastructure,
            "FIAAS_ENVIRONMENT": config.environment,
            "CONSTRETTO_TAGS": ",".join(("kubernetes-{}".format(config.environment), "kubernetes", config.environment)),
            "LOG_STDOUT": "true",
            "LOG_FORMAT": "json"
        }
        self._global_env = config.global_env

    def deploy(self, app_spec, selector, labels):
        LOG.info("Creating new deployment for %s", app_spec.name)
        metadata = ObjectMeta(name=app_spec.name, namespace=app_spec.namespace, labels=labels)
        container_ports = [ContainerPort(name=port_spec.name, containerPort=port_spec.target_port) for port_spec in
                           app_spec.ports]
        env = self._make_env(app_spec)
        pull_policy = "IfNotPresent" if (":" in app_spec.image and ":latest" not in app_spec.image) else "Always"

        container = Container(name=app_spec.name,
                              image=app_spec.image,
                              ports=container_ports,
                              env=env,
                              livenessProbe=_make_probe(app_spec.health_checks.liveness),
                              readinessProbe=_make_probe(app_spec.health_checks.readiness),
                              imagePullPolicy=pull_policy,
                              volumeMounts=self._make_volume_mounts(app_spec),
                              resources=_make_resource_requirements(app_spec.resources))
        service_account_name = "default" if app_spec.admin_access else "fiaas-no-access"

        pod_spec = PodSpec(containers=[container],
                           volumes=self._make_volumes(app_spec),
                           serviceAccountName=service_account_name)

        prom_annotations = _make_prometheus_annotations(app_spec) \
            if app_spec.prometheus and app_spec.prometheus.enabled else None

        pod_labels = _add_status_label(labels)
        selector_labels = _add_status_label(selector)
        pod_metadata = ObjectMeta(name=app_spec.name, namespace=app_spec.namespace, labels=pod_labels,
                                  annotations=prom_annotations)
        pod_template_spec = PodTemplateSpec(metadata=pod_metadata, spec=pod_spec)
        replicas = app_spec.replicas
        # we must avoid that the deployment scales up to app_spec.replicas if autoscaler has set another value
        if should_have_autoscaler(app_spec):
            try:
                deployment = Deployment.get(app_spec.name, app_spec.namespace)
                replicas = deployment.spec.replicas
            except NotFound:
                pass

        spec = DeploymentSpec(replicas=replicas, selector=LabelSelector(matchLabels=selector_labels),
                              template=pod_template_spec, revisionHistoryLimit=5)

        deployment = Deployment.get_or_create(metadata=metadata, spec=spec)
        deployment.save()

    def delete(self, app_spec):
        LOG.info("Deleting deployment for %s", app_spec.name)
        try:
            body = {"kind": "DeleteOptions", "apiVersion": "v1", "propagationPolicy": "Foreground"}
            Deployment.delete(app_spec.name, app_spec.namespace, body=body)
        except NotFound:
            pass

    @staticmethod
    def _make_volumes(app_spec):
        volumes = []
        if app_spec.has_secrets:
            volumes.append(Volume(name=app_spec.name, secret=SecretVolumeSource(secretName=app_spec.name)))
        if app_spec.config.volume:
            volumes.append(Volume(name=app_spec.name, configMap=ConfigMapVolumeSource(name=app_spec.name)))
        return volumes

    @staticmethod
    def _make_volume_mounts(app_spec):
        volume_mounts = []
        if app_spec.has_secrets:
            volume_mounts.append(VolumeMount(name=app_spec.name, readOnly=True, mountPath="/var/run/secrets/fiaas/"))
        if app_spec.config.volume:
            volume_mounts.append(VolumeMount(name=app_spec.name, readOnly=True, mountPath="/var/run/config/fiaas/"))
        return volume_mounts

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

        if app_spec.config.envs:
            env.extend(
                EnvVar(
                    name=name,
                    valueFrom=EnvVarSource(
                        configMapKeyRef=ConfigMapKeySelector(
                            name=app_spec.name,
                            key=name
                        )
                    )
                ) for name in app_spec.config.envs
            )
        return env


def _add_status_label(labels):
    copy = labels.copy()
    copy.update({
        "fiaas/status": "active"
    })
    return labels


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
