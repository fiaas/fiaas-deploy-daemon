#!/usr/bin/env python
# -*- coding: utf-8

# Copyright 2017-2019 The FIAAS Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import json
import logging
import os

from .hyperkit import HyperKitDriver
from .kvm import KVMDriver, KVM2Driver
from .virtualbox import VBoxDriverLinux, VBoxDriverMac
from .xhyve import XHyveDriver

LOG = logging.getLogger(__name__)
DRIVERS = [HyperKitDriver(), XHyveDriver(), KVMDriver(), KVM2Driver(), VBoxDriverLinux(), VBoxDriverMac()]


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
