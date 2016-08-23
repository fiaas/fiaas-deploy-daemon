#!/usr/bin/env python
# -*- coding: utf-8

import logging
from itertools import chain

from k8s import config as k8s_config
from k8s.models.common import ObjectMeta
from k8s.models.ingress import Ingress, IngressSpec, IngressRule, HTTPIngressRuleValue, HTTPIngressPath, IngressBackend
from k8s.models.pod import ContainerPort, EnvVar, HTTPGetAction, TCPSocketAction, Probe, Container, PodSpec, \
    VolumeMount, Volume, SecretVolumeSource, ResourceRequirements
from k8s.models.deployment import Deployment, DeploymentSpec, PodTemplateSpec, LabelsSelector
from k8s.models.service import Service, ServicePort, ServiceSpec

from gke import Gke

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

DEFAULT_SERVICE_WHITELIST = ['80.91.33.141/32', '80.91.33.151/32', '80.91.33.147/32']

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
            "CONSTRETTO_TAGS": ",".join(("kubernetes-" + _cluster_env, "kubernetes", _cluster_env)),
            "LOG_STDOUT": "true",
            "LOG_FORMAT": "json"
        }
        self.infrastructure = config.infrastructure
        self.gke = Gke(_cluster_env) if self.infrastructure == INFRASTRUCTURE_GKE else None

    def deploy(self, app_spec):
        if self.infrastructure == INFRASTRUCTURE_GKE:
            ip = self.gke.get_or_create_static_ip(app_spec.name)
            self._deploy_loadbalancer_service(app_spec, ip)
            self.gke.get_or_create_dns(app_spec.name, ip)

        elif self.infrastructure == INFRASTRUCTURE_DIY:
            self._deploy_services(app_spec)
            self._deploy_ingress(app_spec)
            # TODO: Remove this
            # in dev: Deploy ingress for dev-k8s.finntech.no as well as for k8s.dev.finn.no while migrating off dev-k8s.finntech.no
            if self.target_cluster == "dev":
                old_ingress_suffix = 'dev-k8s.finntech.no'
                self._deploy_ingress(app_spec, name='{}-{}'.format(app_spec.name, old_ingress_suffix),
                                     host='{}.{}'.format(app_spec.name, old_ingress_suffix))
        else:
            raise ValueError("{} is not a valid infrastructure".format(self.infrastructure))
        self._deploy_deployment(app_spec)

    def _deploy_services(self, app_spec):
        LOG.info("Creating/updating services for %s", app_spec.name)

        http_service_ports = \
            [self._make_service_port(service) for service in app_spec.services if service.type == "http"]
        if http_service_ports:
            self._deploy_service(app_spec, "http", http_service_ports)

        thrift_service_ports = \
            [self._make_node_port(service) for service in app_spec.services if service.type == "thrift"]
        if thrift_service_ports:
            self._deploy_service(app_spec, "thrift", thrift_service_ports)

    def _deploy_loadbalancer_service(self, app_spec, ip):
        ports = [self._make_service_port(service) for service in app_spec.services]
        selector = self._make_selector(app_spec)
        labels = self._make_labels(app_spec)
        lb_source_ranges = self._make_loadbalancer_source_ranges(app_spec)
        # add default whitelist to ensure loadBalancer firewall is not 0.0.0.0/0
        lb_source_ranges += DEFAULT_SERVICE_WHITELIST
        metadata = ObjectMeta(name=app_spec.name, namespace=app_spec.namespace, labels=labels)
        spec = ServiceSpec(selector=selector, ports=ports,
                           loadBalancerIP=ip, type="LoadBalancer", loadBalancerSourceRanges=lb_source_ranges)
        svc = Service.get_or_create(metadata=metadata, spec=spec)
        svc.save()

    def _deploy_service(self, app_spec, protocol, ports):
        selector = self._make_selector(app_spec)
        labels = self._make_labels(app_spec)
        service_name = app_spec.name

        if protocol == "http":
            service_type = "ClusterIP"
        else:
            service_name += "-" + protocol
            service_type = "NodePort"

        metadata = ObjectMeta(name=service_name, namespace=app_spec.namespace, labels=labels)
        spec = ServiceSpec(selector=selector, ports=ports, type=service_type)
        svc = Service.get_or_create(metadata=metadata, spec=spec)
        svc.save()

    def _deploy_deployment(self, app_spec):
        deployment = self._create_new_deployment(app_spec)
        deployment.save()

    def _create_new_deployment(self, app_spec):
        LOG.info("Creating new deployment for %s", app_spec.name)
        labels = self._make_labels(app_spec)
        metadata = ObjectMeta(name=app_spec.name, namespace=app_spec.namespace, labels=labels)
        container_ports = [ContainerPort(name=service.name, containerPort=service.exposed_port) for service in app_spec.services]
        main_service = app_spec.services[0]

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
                              livenessProbe=self._make_probe(main_service.liveness, main_service.probe_delay),
                              readinessProbe=self._make_probe(main_service.readiness, main_service.probe_delay),
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

        prom_annotations = self._make_prometheus_annotations(main_service) \
            if not app_spec.prometheus or app_spec.prometheus.enabled else None

        pod_labels = self._add_status_label(labels)
        selector_labels = self._add_status_label(self._make_selector(app_spec))
        pod_metadata = ObjectMeta(name=app_spec.name, namespace=app_spec.namespace, labels=pod_labels, annotations=prom_annotations)
        pod_template_spec = PodTemplateSpec(metadata=pod_metadata, spec=pod_spec)
        spec = DeploymentSpec(replicas=app_spec.replicas, selector=LabelsSelector(matchLabels=selector_labels), template=pod_template_spec)
        deployment = Deployment.get_or_create(metadata=metadata, spec=spec)

        return deployment

    @staticmethod
    def _add_status_label(labels):
        copy = labels.copy()
        copy.update({
            "fiaas/status": "active"
        })
        return labels

    @staticmethod
    def _make_prometheus_annotations(main_service):
        return {
                "prometheus.io/scrape": "true",
                "prometheus.io/port": str(main_service.exposed_port),
                "prometheus.io/path": "/internal-backstage/prometheus"
            }

    def _deploy_ingress(self, app_spec, name=None, host=None):
        name = app_spec.name if name is None else name
        host = self._make_ingress_host(app_spec) if host is None else host

        LOG.info("Creating/updating ingress for %s", name)
        labels = self._make_labels(app_spec)
        metadata = ObjectMeta(name=name, namespace=app_spec.namespace, labels=labels)
        http_ingress_paths = [self._make_http_ingress_path(app_spec, service) for service in app_spec.services if service.type == "http"]
        http_ingress_rule = HTTPIngressRuleValue(paths=http_ingress_paths)
        ingress_rule = IngressRule(host=host, http=http_ingress_rule)
        ingress_spec = IngressSpec(rules=[ingress_rule])
        ingress = Ingress.get_or_create(metadata=metadata, spec=ingress_spec)
        ingress.save()

    def _make_env(self, app_spec):
        env = self._env.copy()
        env["ARTIFACT_NAME"] = app_spec.name
        if any(service.type == "thrift" for service in app_spec.services):
            env["THRIFT_HTTP_PORT"] = "8080"

        return [EnvVar(name=name, value=value) for name, value in env.iteritems()]

    def _make_ingress_host(self, app_spec):
        return "{}.{}".format(app_spec.name, INGRESS_SUFFIX[self.target_cluster])

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
    def _make_loadbalancer_source_ranges(app_spec):
        return list(chain.from_iterable(
            (ip_range.strip() for ip_range in service.whitelist.split(",") if ip_range.strip())
            for service in app_spec.services if service.whitelist))

    @staticmethod
    def _make_service_port(service):
        return ServicePort(name=service.name, port=service.service_port, targetPort=service.exposed_port)

    @staticmethod
    def _make_node_port(service):
        return ServicePort(name=service.name + "-thrift", port=service.service_port,
                           nodePort=service.service_port, targetPort=service.exposed_port)

    @staticmethod
    def _make_http_ingress_path(app_spec, service):
        backend = IngressBackend(serviceName=app_spec.name, servicePort=service.service_port)
        http_ingress_path = HTTPIngressPath(path=service.ingress, backend=backend)
        return http_ingress_path

    @staticmethod
    def _make_resource_requirements(resources_spec):
        def as_dict(resource_requirement_spec):
            return {"cpu": resource_requirement_spec.cpu, "memory": resource_requirement_spec.memory}
        return ResourceRequirements(limits=as_dict(resources_spec.limits), requests=as_dict(resources_spec.requests))

    @staticmethod
    def _make_probe(probe_spec, probe_delay):
        if probe_spec.type == "http":
            action = HTTPGetAction(port=probe_spec.name, path=probe_spec.path)
            return Probe(httpGet=action, initialDelaySeconds=probe_delay)
        else:
            action = TCPSocketAction(port=probe_spec.name)
            return Probe(tcpSocket=action, initialDelaySeconds=probe_delay)

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
