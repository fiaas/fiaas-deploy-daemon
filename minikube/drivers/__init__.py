#!/usr/bin/env python
# -*- coding: utf-8
import json
import os
import logging

from .virtualbox import VBoxDriverLinux, VBoxDriverMac
from .xhyve import XHyveDriver
from .hyperkit import HyperKitDriver
from .kvm import KVMDriver

LOG = logging.getLogger(__name__)
DRIVERS = [HyperKitDriver(), XHyveDriver(), KVMDriver(), VBoxDriverLinux(), VBoxDriverMac()]


def _find_configured_driver():
    try:
        with open(os.path.expanduser("~/.minikube/config/config.json")) as fobj:
            config = json.load(fobj)
            return config.get("vm-driver")
    except IOError:
        LOG.debug("Failed to open minikube config")
        return None


def select_driver(minikube_version):
    configured_driver_name = _find_configured_driver()
    supported_drivers = [driver for driver in DRIVERS if driver.supported(minikube_version)]
    for driver in supported_drivers:
        if configured_driver_name is None or configured_driver_name == driver.name:
            LOG.debug("Selected driver %s%s", driver.name, " from configuration" if configured_driver_name else "")
            return driver
    if supported_drivers:
        driver = supported_drivers[0]
        LOG.warning("The configured driver %s does not seem to be supported, using %s instead",
                    configured_driver_name, driver.name)
        return driver
    raise MinikubeDriverError("No supported drivers available")


class MinikubeDriverError(Exception):
    pass
