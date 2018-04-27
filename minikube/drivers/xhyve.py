#!/usr/bin/env python
# -*- coding: utf-8
from distutils.version import StrictVersion

from .common import has_utility, MacDriver


class XHyveDriver(MacDriver):
    name = "xhyve"

    def supported(self, minikube_version):
        if minikube_version < StrictVersion("0.5"):
            return False
        return has_utility('docker-machine-driver-xhyve')
