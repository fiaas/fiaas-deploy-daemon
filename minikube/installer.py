#!/usr/bin/env python
# -*- coding: utf-8
import hashlib
import json
import logging
import random
import shutil
import string
import tempfile
from distutils.version import StrictVersion

import appdirs
import datetime
import os
import requests

from .drivers import select_driver
from .minikube import Minikube, MinikubeError

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())
CACHE_DIR = appdirs.user_cache_dir("minikube", "schibsted.io")


class MinikubeInstaller(object):
    def __init__(self, minikube_version=None, workdir=None):
        cache_root = os.path.join(CACHE_DIR, "releases")
        _makedirs(cache_root)
        self._minikube_version = _resolve_minikube_version(minikube_version)
        self._driver = select_driver(self._minikube_version)
        self._workdir = tempfile.mkdtemp(prefix="minikube-") if workdir is None else workdir
        self._cachedir = os.path.join(cache_root, self._minikube_version.org)
        _makedirs(self._cachedir)

    def install(self):
        path, downloaded_digest = self._download_binary()
        wanted_digest = self._get_wanted_checksum()
        if wanted_digest != downloaded_digest:
            msg = "Downloaded binary differ! (Wanted: %s != Downloaded: %s)" % (wanted_digest, downloaded_digest)
            raise MinikubeError(msg)
        mode = os.stat(path).st_mode
        mode |= (mode & 0o444) >> 2  # copy R bits to X
        os.chmod(path, mode)
        LOG.debug("Downloaded minikube-%s-%s to %s", self._driver.os, self._driver.arch, path)
        return path

    def _download_binary(self):
        filename = "minikube-{os}-{arch}".format(os=self._driver.os, arch=self._driver.arch)
        cache_path = os.path.join(self._cachedir, filename)
        sha = hashlib.sha256()
        if os.path.exists(cache_path):
            with open(cache_path) as fobj:
                sha.update(fobj.read())
            return cache_path, sha.hexdigest()
        url = "https://storage.googleapis.com/minikube/releases/{version}/{filename}".format(
            version=self._minikube_version.org, filename=filename)
        resp = requests.get(url, stream=True)
        if resp.status_code != 200:
            raise MinikubeError("Error downloading minikube from %s. HTTP status %d" % (url, resp.status_code))
        sha = hashlib.sha256()
        with open(cache_path, "wb") as fobj:
            for chunk in resp.iter_content(chunk_size=16 * 1024):
                sha.update(chunk)
                fobj.write(chunk)
        return cache_path, sha.hexdigest()

    def _get_wanted_checksum(self):
        filename = "minikube-{os}-{arch}.sha256".format(os=self._driver.os, arch=self._driver.arch)
        cache_path = os.path.join(self._cachedir, filename)
        if os.path.exists(cache_path):
            with open(cache_path) as fobj:
                return fobj.read()
        url = "https://storage.googleapis.com/minikube/releases/{version}/{filename}".format(
            version=self._minikube_version.org, filename=filename)
        if self._minikube_version == StrictVersion("0.20") and self._driver.os == "linux" and self._driver.arch == "amd64":
            # This version had invalid checksums on github.com, so use hardcoded digest
            return "f7447a37332879b934bf7fcae97327367a5b92d33d12ea24301c212892efe326"
        resp = requests.get(url)
        if resp.status_code != 200:
            raise MinikubeError("Could not download SHA of binary. HTTP status %d" % resp.status_code)
        digest = resp.text.strip()
        with open(cache_path, "w") as fobj:
            fobj.write(digest)
        return digest

    def new(self, k8s_version=None, profile=None):
        letters = list(string.ascii_letters)
        random.shuffle(letters)
        id = profile + "".join(letters)
        vm = Minikube(self._workdir, self._driver, k8s_version, id)
        return vm

    def cleanup(self):
        shutil.rmtree(self._workdir, ignore_errors=True)


def _resolve_minikube_version(minikube_version):
    if minikube_version:
        version = StrictVersion(minikube_version[1:])
        version.org = minikube_version
    else:
        data = _get_release_data()
        try:
            original_version = data["name"]
            version = StrictVersion(original_version[1:])
            version.org = original_version
        except KeyError:
            raise MinikubeError("Found no name in JSON for latest release of minikube")
    return version


def _get_release_data():
    cache_path = os.path.join(CACHE_DIR, "releases", "latest.json")
    if os.path.exists(cache_path):
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(cache_path))
        age = datetime.datetime.now() - mtime
        if age < datetime.timedelta(days=7):
            with open(cache_path) as fobj:
                return json.load(fobj)
    resp = requests.get("https://api.github.com/repos/kubernetes/minikube/releases/latest")
    if resp.status_code != 200:
        raise MinikubeError("GitHub responded with status %d when trying to find latest release" % resp.status_code)
    data = resp.json()
    with open(cache_path, "w") as fobj:
        json.dump(data, fobj)
    return data


def _makedirs(path):
    try:
        os.makedirs(path)
    except OSError:
        if not os.path.exists(path):
            raise
