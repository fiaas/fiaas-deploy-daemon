#!/usr/bin/env python
# -*- coding: utf-8
import subprocess

from .common import has_utility, is_macos, LinuxDriver, MacDriver


class VBoxDriverBase(object):
    name = "virtualbox"

    def supported(self, minikube_version):
        return self._is_correct_os() and has_utility("VBoxManage") and self._is_vtx_enabled()

    def _is_vtx_enabled(self):
        raise NotImplementedError()

    def _is_correct_os(self):
        raise NotImplementedError()


class VBoxDriverLinux(VBoxDriverBase, LinuxDriver):
    def _is_correct_os(self):
        return not is_macos()

    def _is_vtx_enabled(self):
        try:
            with open("/proc/cpuinfo") as fobj:
                cpu_info = fobj.read()
            return any(v in cpu_info for v in ("vmx", "svm"))
        except IOError:
            return False


class VBoxDriverMac(VBoxDriverBase, MacDriver):
    def _is_correct_os(self):
        return is_macos()

    def _is_vtx_enabled(self):
        try:
            output = subprocess.check_output(["sysctl", "machdep.cpu.features"])
            return "VMX" in output
        except subprocess.CalledProcessError:
            return False
