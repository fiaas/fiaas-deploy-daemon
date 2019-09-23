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

import itertools
import subprocess

import yaml
from k8s import config
from k8s.models.namespace import Namespace
from tqdm import tqdm

from fiaas_deploy_daemon.tpr.types import PaasbetaStatus

"""Requires `tqdm`, which is not usually part of our requirements."""


def _configure():
    output = subprocess.check_output(["kubectl", "config", "view", "--minify"])
    kube = yaml.safe_load(output)
    config.api_server = kube["clusters"][0]["cluster"]["server"]
    config.api_token = kube["users"][0]["user"]["token"]


def _clean_app(statuses):
    statuses = sorted(statuses, key=_get_creation)
    for status in tqdm(statuses[:-20], desc="Statuses    ", unit="statuses"):
        PaasbetaStatus.delete(status.metadata.name, status.metadata.namespace)


def _clean_namespace(namespace):
    statuses = PaasbetaStatus.list(namespace)
    statuses = sorted(statuses, key=_get_app)
    apps = {}
    for app, app_statuses in itertools.groupby(statuses, _get_app):
        apps[app] = list(app_statuses)
    with tqdm(apps, desc="Applications", unit="app") as t:
        for app in t:
            t.set_postfix(app=app)
            _clean_app(apps[app])


def _get_app(s):
    return s.metadata.labels["app"]


def _get_creation(s):
    return s.metadata.creationTimestamp


def main():
    _configure()
    namespaces = [n.metadata.name for n in Namespace.list(namespace=None)]
    with tqdm(namespaces, desc="Namespaces  ", unit="ns") as t:
        for namespace in t:
            t.set_postfix(ns=namespace)
            _clean_namespace(namespace)


if __name__ == "__main__":
    main()
