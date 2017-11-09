#!/usr/bin/env python
# -*- coding: utf-8
import subprocess
import time
from urlparse import urljoin

import os
import requests
import yaml
from monotonic import monotonic as time_monotonic

PATIENCE = 30


class Minikube(object):
    kubeconfig = None
    server = None
    client_cert = None
    client_key = None
    api_cert = None

    def __init__(self, workdir, driver, k8s_version=None, profile=None):
        path = os.path.join(workdir, "minikube")
        if not os.path.exists(path):
            raise MinikubeError("Minikube is not installed at %s" % path)
        self._path = path
        self.kubeconfig = os.path.join(workdir, "kubeconfig")
        self._env = os.environ.copy()
        self._env["KUBECONFIG"] = self.kubeconfig
        self._driver = driver
        self._k8s_version = k8s_version
        self._profile = profile

    def _set_attributes(self):
        def find_named_item(name, l):
            for item in l:
                if item[u"name"] == name:
                    return item
            raise MinikubeError("Unable to find item matching selected name (%s)" % name)

        with open(self.kubeconfig, "r") as fobj:
            config = yaml.safe_load(fobj)
        try:
            context = find_named_item(self._profile, config[u"contexts"])[u"context"]
            cluster = find_named_item(context[u"cluster"], config[u"clusters"])[u"cluster"]
            self.server = cluster[u"server"]
            self.api_cert = cluster[u"certificate-authority"]
            user = find_named_item(context[u"user"], config[u"users"])[u"user"]
            self.client_cert = user[u"client-certificate"]
            self.client_key = user[u"client-key"]
        except KeyError as e:
            raise MinikubeError("Unable to read configuration for selected context: %s" % str(e))

    def _api_is_up(self):
        try:
            resp = requests.get(urljoin(self.server, "version"),
                                cert=(self.client_cert, self.client_key),
                                verify=self.api_cert,
                                timeout=1)
        except requests.RequestException:
            return False
        return resp.status_code == 200

    def start(self):
        extra_params = ["--keep-context"]
        if self._k8s_version:
            extra_params.extend(("--kubernetes-version", self._k8s_version))
        extra_params.extend(self._driver.arguments)
        running = self._attempt_start(extra_params)
        start = time_monotonic()
        while not running and time_monotonic() < (start + PATIENCE):
            running = self._attempt_start(extra_params)
        if not running:
            raise MinikubeError("Gave up starting minikube after %d seconds" % PATIENCE)

    def _attempt_start(self, extra_params):
        self._execute("start", extra_params)
        time.sleep(1)
        self._set_attributes()
        running = self._api_is_up()
        return running

    def stop(self):
        self._execute("stop")

    def delete(self):
        self._execute("delete", ignore_errors=True)

    def _execute(self, operation, extra_params=None, ignore_errors=False):
        cmd = [self._path, operation]
        if extra_params:
            cmd.extend(extra_params)
        if self._profile:
            cmd.extend(("--profile", self._profile))
        try:
            subprocess.check_call(cmd, env=self._env)
        except subprocess.CalledProcessError as e:
            if not ignore_errors:
                raise MinikubeError(e)


class MinikubeError(Exception):
    pass
