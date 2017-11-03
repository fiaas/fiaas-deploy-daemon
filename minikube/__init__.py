#!/usr/bin/env python
# -*- coding: utf-8

import hashlib
import logging
import random
import string
import subprocess
import tempfile
import time
from urlparse import urljoin

import os
import requests
import shutil
import yaml
from distutils.version import StrictVersion
from monotonic import monotonic as time_monotonic

from .drivers import select_driver

PATIENCE = 30

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())


class MinikubeInstaller(object):
    def __init__(self, minikube_version=None, workdir=None):
        self._minikube_version = self._resolve_minikube_version(minikube_version)
        self._driver = select_driver(self._minikube_version)
        self._workdir = tempfile.mkdtemp(prefix="minikube-") if workdir is None else workdir

    def install(self):
        url = "https://storage.googleapis.com/minikube/releases/{version}/minikube-{os}-{arch}".format(
            version=self._minikube_version.org, os=self._driver.os, arch=self._driver.arch)
        path, downloaded_digest = self._download_binary(url)
        wanted_digest = self._get_wanted_checksum(url)
        if wanted_digest != downloaded_digest:
            msg = "Downloaded binary differ! (Wanted: %s != Downloaded: %s)" % (wanted_digest, downloaded_digest)
            raise MinikubeError(msg)
        mode = os.stat(path).st_mode
        mode |= (mode & 0o444) >> 2  # copy R bits to X
        os.chmod(path, mode)
        logging.debug("Downloaded minikube-%s-%s to %s", self._driver.os, self._driver.arch, path)
        return path

    def _download_binary(self, url):
        resp = requests.get(url, stream=True)
        if resp.status_code != 200:
            raise MinikubeError("Error downloading minikube from %s. HTTP status %d" % (url, resp.status_code))
        sha = hashlib.sha256()
        path = os.path.join(self._workdir, "minikube")
        with open(path, "wb") as fobj:
            for chunk in resp.iter_content(chunk_size=16 * 1024):
                sha.update(chunk)
                fobj.write(chunk)
        return path, sha.hexdigest()

    def _get_wanted_checksum(self, url):
        if (self._minikube_version == StrictVersion("0.20") and self._driver.os == "linux"
                and self._driver.arch == "amd64"):
            # This version had invalid checksums on github.com, so use hardcoded digest
            return "f7447a37332879b934bf7fcae97327367a5b92d33d12ea24301c212892efe326"
        sha_url = url + ".sha256"
        resp = requests.get(sha_url)
        if resp.status_code != 200:
            raise MinikubeError("Could not download SHA of binary. HTTP status %d" % resp.status_code)
        digest = resp.text.strip()
        return digest

    def new(self, k8s_version=None, profile=None):
        letters = list(string.ascii_letters)
        random.shuffle(letters)
        id = profile + "".join(letters)
        vm = Minikube(self._workdir, self._driver, k8s_version, id)
        return vm

    def cleanup(self):
        shutil.rmtree(self._workdir, ignore_errors=True)

    @staticmethod
    def _resolve_minikube_version(minikube_version):
        if minikube_version:
            version = StrictVersion(minikube_version[1:])
            version.org = minikube_version
        else:
            resp = requests.get("https://api.github.com/repos/kubernetes/minikube/releases/latest")
            if resp.status_code != 200:
                raise MinikubeError("GitHub responded with status %d when trying to find latest release" % resp.status_code)
            data = resp.json()
            try:
                original_version = data["name"]
                version = StrictVersion(original_version[1:])
                version.org = original_version
            except KeyError:
                raise MinikubeError("Found no name in JSON for latest release of minikube")
        return version


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
