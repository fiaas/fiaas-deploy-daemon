#!/usr/bin/env python
# -*- coding: utf-8

import logging

from .virtualbox import VBoxDriverLinux, VBoxDriverMac
from .xhyve import XHyveDriver


DRIVERS = [XHyveDriver(), VBoxDriverLinux(), VBoxDriverMac()]


def select_driver(minikube_version):
    for driver in DRIVERS:
        if driver.supported(minikube_version):
            logging.debug("Selected driver %s", driver.name)
            return driver
    from .. import MinikubeError
    raise MinikubeError("No supported drivers available")
