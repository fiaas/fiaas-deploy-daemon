#!/usr/bin/env python
# -*- coding: utf-8

from collections import namedtuple


class BaseSpec(object):
    def __repr__(self):
        return "{}({})".format(self.__class__.__name__,
                               ", ".join("{}={}".format(key, self.__dict__[key]) for key in vars(self) if not key.startswith("_"))
                               )


ProbeSpec = namedtuple("ProbeSpec", ["name", "type", "path"])


class AppSpec(BaseSpec):
    """Specify the necessary details for deploying an app"""

    def __init__(self, namespace, name, image, services, replicas, resources, admin_access, has_secrets):
        """
        :param namespace: Name space of application
        :param name: Name of application
        :param image: Reference to docker image
        :param services: A list of ServiceSpecs
        :param replicas: Number of replicas
        :param resources: Resource limits and requests
        :param admin_access: Access to the api server
        :param has_secrets: Does the container have secrets that should be loaded
        """
        self.namespace = namespace
        self.name = name
        self.image = image
        if services:
            iter(services)  # Check for iterability
        self.services = services
        self.replicas = replicas
        self.resources = resources
        self.admin_access = admin_access
        self.has_secrets = has_secrets

    @property
    def version(self):
        if ":" not in self.image:
            return "<unknown>"
        return self.image.split(":")[-1]


class ServiceSpec(BaseSpec):
    """Specify a service"""

    def __init__(self, exposed_port, service_port, type="http", ingress=u"/", readiness=u"/", liveness=u"/", probe_delay=5):
        """
        :param ingress:
        :param exposed_port: Exposed port in container
        :param service_port: Port to use for service
        :param type: Type of service (http or thrift)
        :param ingress: Ingress path for application root
        :param readiness: Path for readiness-probe (only for http) (Default: /)
        :param liveness: Path for liveness-probe (only for http) (Default: /)
        :param probe_delay: How long to wait before starting probes (Default: 10s)
        """
        self.name = "{}{}".format(type, exposed_port)
        self.exposed_port = exposed_port
        self.service_port = service_port
        self.type = type
        self.ingress = ingress
        self.readiness = ProbeSpec(self.exposed_port, type, readiness)
        self.liveness = ProbeSpec(self.exposed_port, type, liveness)
        self.probe_delay = probe_delay


class ResourceRequirementSpec(BaseSpec):
    def __init__(self, cpu=None, memory=None):
        self.cpu = cpu
        self.memory = memory


class ResourcesSpec(BaseSpec):
    "Specify resources required by the app"

    def __init__(self, limits=None, requests=None):
        self.limits = limits
        self.requests = requests
