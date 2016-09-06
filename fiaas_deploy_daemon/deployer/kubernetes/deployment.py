#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import logging
import shlex

from k8s.models.common import ObjectMeta
from k8s.models.deployment import Deployment, DeploymentSpec, PodTemplateSpec, LabelsSelector
from k8s.models.pod import ContainerPort, EnvVar, HTTPGetAction, TCPSocketAction, ExecAction, HTTPHeader, Container, \
    PodSpec, VolumeMount, Volume, SecretVolumeSource, ResourceRequirements, Probe

LOG = logging.getLogger(__name__)

CLUSTER_ENV_MAPPING = {
    "prod1": "prod"
}


class DeploymentDeployer(object):
    def __init__(self, config):
        _cluster_env = _resolve_cluster_env(config.target_cluster)
        self._env = {
            "FINN_ENV": _cluster_env,
            "FIAAS_INFRASTRUCTURE": config.infrastructure,
            "CONSTRETTO_TAGS": ",".join(("kubernetes-{}".format(_cluster_env), "kubernetes", _cluster_env)),
            "LOG_STDOUT": "true",
            "LOG_FORMAT": "json"
        }

    def deploy(self, app_spec, selector, labels):
        LOG.info("Creating new deployment for %s", app_spec.name)
        metadata = ObjectMeta(name=app_spec.name, namespace=app_spec.namespace, labels=labels)
        container_ports = [ContainerPort(name=port_spec.name, containerPort=port_spec.target_port) for port_spec in app_spec.ports]
        env = self._make_env(app_spec)
        env.append(EnvVar(name="IMAGE", value=app_spec.image))
        env.append(EnvVar(name="VERSION", value=app_spec.version))
        pull_policy = "IfNotPresent" if (":" in app_spec.image and ":latest" not in app_spec.image) else "Always"

        secrets_volume_mounts = [VolumeMount(name=app_spec.name, readOnly=True, mountPath="/var/run/secrets/fiaas/")] \
            if app_spec.has_secrets else []

        container = Container(name=app_spec.name,
                              image=app_spec.image,
                              ports=container_ports,
                              env=env,
                              livenessProbe=_make_probe(app_spec.health_checks.liveness),
                              readinessProbe=_make_probe(app_spec.health_checks.readiness),
                              imagePullPolicy=pull_policy,
                              volumeMounts=secrets_volume_mounts,
                              resources=_make_resource_requirements(app_spec.resources))
        secrets_volumes = [Volume(name=app_spec.name, secret=SecretVolumeSource(secretName=app_spec.name))] \
            if app_spec.has_secrets else []

        # currently only supports read and no access
        service_account_name = "default" if app_spec.admin_access == "read-write" else "fiaas-no-access"

        pod_spec = PodSpec(containers=[container],
                           volumes=secrets_volumes,
                           serviceAccountName=service_account_name)

        prom_annotations = _make_prometheus_annotations(app_spec.prometheus) \
            if app_spec.prometheus and app_spec.prometheus.enabled else None

        pod_labels = _add_status_label(labels)
        selector_labels = _add_status_label(selector)
        pod_metadata = ObjectMeta(name=app_spec.name, namespace=app_spec.namespace, labels=pod_labels, annotations=prom_annotations)
        pod_template_spec = PodTemplateSpec(metadata=pod_metadata, spec=pod_spec)
        spec = DeploymentSpec(replicas=app_spec.replicas, selector=LabelsSelector(matchLabels=selector_labels), template=pod_template_spec)
        deployment = Deployment.get_or_create(metadata=metadata, spec=spec)
        deployment.save()

    def _make_env(self, app_spec):
        env = self._env.copy()
        env["ARTIFACT_NAME"] = app_spec.name
        return [EnvVar(name=name, value=value) for name, value in env.iteritems()]


def _add_status_label(labels):
    copy = labels.copy()
    copy.update({
        "fiaas/status": "active"
    })
    return labels


def _make_prometheus_annotations(prometheus_spec):
    return {
        "prometheus.io/scrape": str(prometheus_spec.enabled).lower(),
        "prometheus.io/port": str(prometheus_spec.port),
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
        raise RuntimeError("AppSpec must have exactly one healthcheck, none was defined.")

    return probe


def _resolve_cluster_env(target_cluster):
    if target_cluster in CLUSTER_ENV_MAPPING:
        return CLUSTER_ENV_MAPPING[target_cluster]
    else:
        return target_cluster
