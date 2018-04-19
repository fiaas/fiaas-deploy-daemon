#!/usr/bin/env python
# -*- coding: utf-8
from distutils.version import StrictVersion

from .common import has_utility, LinuxDriver


class KVMDriver(LinuxDriver):
    arguments = ("--vm-driver", "kvm")

    def supported(self, minikube_version):
        if minikube_version < StrictVersion("0.5"):
            return False
        return has_utility("docker-machine-driver-kvm")
