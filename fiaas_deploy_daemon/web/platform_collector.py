#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import unicode_literals

import platform

from prometheus_client.core import GaugeMetricFamily, REGISTRY

_COMMON_SYSTEM_LABELS = ("system", "name", "kernel", "version")


class PlatformCollector(object):
    """Collector for platform information"""

    def __init__(self, registry=REGISTRY):
        self._metrics = [
            self._python(),
            self._machine(),
            self._system()
        ]
        if registry:
            registry.register(self)

    def collect(self):
        return self._metrics

    @staticmethod
    def _python():
        g = GaugeMetricFamily("python_info", "Python information",
                              labels=("version", "implementation", "major", "minor", "patchlevel"))
        version = platform.python_version()
        impl = platform.python_implementation()
        major, minor, patchlevel = platform.python_version_tuple()
        g.add_metric((version, impl, major, minor, patchlevel), 1)
        return g

    @staticmethod
    def _machine():
        g = GaugeMetricFamily("machine_info", "Machine information", labels=(
            "bits", "linkage", "machine", "processor"))
        system, node, release, version, machine, processor = platform.uname()
        g.add_metric(platform.architecture() + (machine, processor), 1)
        return g

    def _system(self):
        """Expose information about the system

        Common to all systems:
            - system: Windows, Linux, Darwin, Java
            - name: Darwin, Windows 10, Funtoo Linux etc.
            - kernel: Kernel version
            - version: Version of the OS

        Some systems may add extra information
        """
        return {
            "Linux": self._linux,
            "Windows": self._win32,
            "Java": self._java,
            "Darwin": self._mac,
        }.get(platform.system(), self._system_common)()

    @staticmethod
    def _system_common():
        g = GaugeMetricFamily("system_info", "System information", labels=_COMMON_SYSTEM_LABELS)
        system, node, release, version, machine, processor = platform.uname()
        g.add_metric((system, "", release, version), 1)
        return g

    @staticmethod
    def _java():
        labels = _COMMON_SYSTEM_LABELS + ("java_version", "vm_release", "vm_vendor", "vm_name")
        g = GaugeMetricFamily("system_info", "System information (Jython)", labels=labels)
        java_version, vendor, vminfo, osinfo = platform.java_ver()
        vm_name, vm_release, vm_vendor = vminfo
        system, kernel, _ = osinfo
        g.add_metric((system, "Java", kernel, "", java_version, vm_release, vm_vendor, vm_name), 1)
        return g

    @staticmethod
    def _win32():
        g = GaugeMetricFamily("system_info", "System information (Windows)",
                              labels=_COMMON_SYSTEM_LABELS + ("csd", "ptype"))
        release, version, csd, ptype = platform.win32_ver()
        g.add_metric(("Windows", "Windows {}".format(release), version, version, csd, ptype), 1)
        return g

    @staticmethod
    def _mac():
        g = GaugeMetricFamily("system_info", "System information (Mac OSX)",
                              labels=_COMMON_SYSTEM_LABELS)
        release, versioninfo, machine = platform.mac_ver()
        _, _, kernel, _, _, _ = platform.uname()
        g.add_metric(("Darwin", "Darwin", kernel, release), 1)
        return g

    @staticmethod
    def _linux():
        g = GaugeMetricFamily("system_info", "System information (Linux)",
                              labels=_COMMON_SYSTEM_LABELS + ("dist_id", "libc", "libc_version"))
        name, version, dist_id = platform.linux_distribution()
        libc, libc_version = platform.libc_ver()
        _, _, kernel, _, _, _ = platform.uname()
        g.add_metric(("Linux", name.strip(), kernel, version, dist_id, libc, libc_version), 1)
        return g


PLATFORM_COLLECTOR = PlatformCollector()
"""PlatfprmCollector in default Registry REGISTRY"""
