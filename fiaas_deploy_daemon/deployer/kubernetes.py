#!/usr/bin/env python
# -*- coding: utf-8

import logging
import shlex

from gke import Gke
from k8s import config as k8s_config
from k8s.models.common import ObjectMeta
from k8s.models.deployment import Deployment, DeploymentSpec, PodTemplateSpec, LabelsSelector
from k8s.models.ingress import Ingress, IngressSpec, IngressRule, HTTPIngressRuleValue, HTTPIngressPath, IngressBackend
from k8s.models.pod import ContainerPort, EnvVar, HTTPGetAction, TCPSocketAction, ExecAction, HTTPHeader, Container, \
    PodSpec, VolumeMount, Volume, SecretVolumeSource, ResourceRequirements, Probe
from k8s.models.service import Service, ServicePort, ServiceSpec

DEFAULT_NAMESPACE = "default"
LOG = logging.getLogger(__name__)
BASE_ANNOTATIONS = {}
INGRESS_SUFFIX = {
    "dev": "k8s.dev.finn.no",
    "local": "127.0.0.1.xip.io",
    "test": "127.0.0.1.xip.io",
    "prod": "k8s1-prod1.z01.finn.no",
}
INFRASTRUCTURE_GKE = "gke"
INFRASTRUCTURE_DIY = "diy"

CLUSTER_ENV_MAPPING = {
    "prod1": "prod"
}


class K8s(object):
    """Adapt from an AppSpec to the necessary definitions for a kubernetes cluster
    """

    def __init__(self, config):
        k8s_config.api_server = config.api_server
        k8s_config.api_token = config.api_token
        if config.api_cert:
            k8s_config.verify_ssl = config.api_cert
        else:
            k8s_config.verify_ssl = not config.debug
        if config.client_cert:
            k8s_config.cert = (config.client_cert, config.client_key)
        k8s_config.debug = config.debug
        self.target_cluster = config.target_cluster
        self.version = config.version
        _cluster_env = self._resolve_cluster_env(self.target_cluster)
        self._env = {
            "FINN_ENV": _cluster_env,
            "FIAAS_INFRASTRUCTURE": config.infrastructure,
            "CONSTRETTO_TAGS": ",".join(("kubernetes" + "-" + _cluster_env, "kubernetes", _cluster_env)),
            "LOG_STDOUT": "true",
            "LOG_FORMAT": "json"
        }
        self.infrastructure = config.infrastructure
        self.gke = Gke(_cluster_env) if self.infrastructure == INFRASTRUCTURE_GKE else None

    def deploy(self, app_spec):
        self._deploy_service(app_spec)
        self._deploy_deployment(app_spec)
        self._deploy_ingress(app_spec)

    def _deploy_service(self, app_spec):
        LOG.info("Creating/updating service for %s", app_spec.name)
        ports = [self._make_service_port(port_spec) for port_spec in app_spec.ports]
        selector = self._make_selector(app_spec)
        labels = self._make_labels(app_spec)
        service_name = app_spec.name
        metadata = ObjectMeta(name=service_name, namespace=app_spec.namespace, labels=labels)
        spec = ServiceSpec(selector=selector, ports=ports, type="ClusterIP")
        svc = Service.get_or_create(metadata=metadata, spec=spec)
        svc.save()

    @staticmethod
    def _make_service_port(port_spec):
        return ServicePort(
            protocol='TCP',
            name=port_spec.name,
            port=port_spec.port,
            targetPort=port_spec.target_port)

    def _deploy_deployment(self, app_spec):
        LOG.info("Creating new deployment for %s", app_spec.name)
        labels = self._make_labels(app_spec)
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
                              livenessProbe=self._make_probe(app_spec.health_checks.liveness),
                              readinessProbe=self._make_probe(app_spec.health_checks.readiness),
                              imagePullPolicy=pull_policy,
                              volumeMounts=secrets_volume_mounts,
                              resources=self._make_resource_requirements(app_spec.resources))
        secrets_volumes = [Volume(name=app_spec.name, secret=SecretVolumeSource(secretName=app_spec.name))] \
            if app_spec.has_secrets else []

        # currently only supports read and no access
        service_account_name = "default" if app_spec.admin_access == "read-write" else "fiaas-no-access"

        pod_spec = PodSpec(containers=[container],
                           volumes=secrets_volumes,
                           serviceAccountName=service_account_name)

        prom_annotations = self._make_prometheus_annotations(app_spec.prometheus) \
            if app_spec.prometheus and app_spec.prometheus.enabled else None

        pod_labels = self._add_status_label(labels)
        selector_labels = self._add_status_label(self._make_selector(app_spec))
        pod_metadata = ObjectMeta(name=app_spec.name, namespace=app_spec.namespace, labels=pod_labels, annotations=prom_annotations)
        pod_template_spec = PodTemplateSpec(metadata=pod_metadata, spec=pod_spec)
        spec = DeploymentSpec(replicas=app_spec.replicas, selector=LabelsSelector(matchLabels=selector_labels), template=pod_template_spec)
        deployment = Deployment.get_or_create(metadata=metadata, spec=spec)
        deployment.save()

    @staticmethod
    def _add_status_label(labels):
        copy = labels.copy()
        copy.update({
            "fiaas/status": "active"
        })
        return labels

    @staticmethod
    def _make_prometheus_annotations(prometheus_spec):
        return {
            "prometheus.io/scrape": str(prometheus_spec.enabled).lower(),
            "prometheus.io/port": str(prometheus_spec.port),
            "prometheus.io/path": prometheus_spec.path
        }

    def _deploy_ingress(self, app_spec):
        if app_spec.host:
            LOG.info("Creating/updating ingress for %s", app_spec.name)
            labels = self._make_labels(app_spec)
            metadata = ObjectMeta(name=app_spec.name, namespace=app_spec.namespace, labels=labels)
            http_ingress_paths = [self._make_http_ingress_path(app_spec, port_spec) for port_spec in app_spec.ports if
                                  port_spec.protocol == u"http"]
            http_ingress_rule = HTTPIngressRuleValue(paths=http_ingress_paths)
            ingress_rule = IngressRule(host=self._make_ingress_host(app_spec.host), http=http_ingress_rule)
            ingress_spec = IngressSpec(rules=[ingress_rule])
            ingress = Ingress.get_or_create(metadata=metadata, spec=ingress_spec)
            ingress.save()
        else:
            Ingress.delete(app_spec.name, app_spec.namespace)

    def _make_env(self, app_spec):
        env = self._env.copy()
        env["ARTIFACT_NAME"] = app_spec.name
        return [EnvVar(name=name, value=value) for name, value in env.iteritems()]

    def _make_ingress_host(self, host):
        if host == "www.finn.no":
            return "{}.finn.no".format(self.target_cluster)
        return "{}.{}".format(self.target_cluster, host)

    def _make_labels(self, app_spec):
        labels = {
            "app": app_spec.name,
            "fiaas/version": app_spec.version,
            "fiaas/deployed_by": self.version,
        }
        return labels

    @staticmethod
    def _make_selector(app_spec):
        return {'app': app_spec.name}

    @staticmethod
    def _make_http_ingress_path(app_spec, port_spec):
        backend = IngressBackend(serviceName=app_spec.name, servicePort=port_spec.port)
        http_ingress_path = HTTPIngressPath(path=port_spec.path, backend=backend)
        return http_ingress_path

    @staticmethod
    def _make_resource_requirements(resources_spec):
        def as_dict(resource_requirement_spec):
            return {"cpu": resource_requirement_spec.cpu, "memory": resource_requirement_spec.memory}

        return ResourceRequirements(limits=as_dict(resources_spec.limits), requests=as_dict(resources_spec.requests))

    @staticmethod
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

    @staticmethod
    def _resolve_cluster_env(target_cluster):
        if target_cluster in CLUSTER_ENV_MAPPING:
            return CLUSTER_ENV_MAPPING[target_cluster]
        else:
            return target_cluster

    @staticmethod
    def _app_version(app_spec):
        if ":" not in app_spec.image:
            return "<unknown>"
        return app_spec.image.split(":")[-1]
