#!/usr/bin/env python
# -*- coding: utf-8
from distutils.version import StrictVersion

from .common import has_utility, MacDriver


class HyperKitDriver(MacDriver):
    name = "hyperkit"

    def supported(self, minikube_version):
        if minikube_version < StrictVersion("0.22.0"):
            return False
        return has_utility('docker-machine-driver-hyperkit')
