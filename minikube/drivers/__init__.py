#!/usr/bin/env python
# -*- coding: utf-8

import logging

from .virtualbox import VBoxDriverLinux, VBoxDriverMac
from .xhyve import XHyveDriver

LOG = logging.getLogger(__name__)
DRIVERS = [XHyveDriver(), VBoxDriverLinux(), VBoxDriverMac()]


def select_driver(minikube_version):
    for driver in DRIVERS:
        if driver.supported(minikube_version):
            LOG.debug("Selected driver %s", driver.name)
            return driver
    raise MinikubeDriverError("No supported drivers available")


class MinikubeDriverError(Exception):
    pass
