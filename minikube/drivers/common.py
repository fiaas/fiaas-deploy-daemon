#!/usr/bin/env python
# -*- coding: utf-8

import os


def has_utility(cmd):
    path = os.environ['PATH']
    return any(os.access(os.path.join(p, cmd), os.X_OK) for p in path.split(os.pathsep))


def is_macos():
    return os.uname()[0] == 'Darwin'


class Driver(object):
    arch = "amd64"

    @property
    def name(self):
        return self.__class__.__name__


class LinuxDriver(Driver):
    os = "linux"


class MacDriver(Driver):
    os = "darwin"
