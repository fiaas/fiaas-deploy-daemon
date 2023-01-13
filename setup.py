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
import os

from setuptools import setup, find_packages


def read(filename):
    with open(os.path.join(os.path.dirname(__file__), filename)) as f:
        return f.read()


GENERIC_REQ = [
    "ConfigArgParse == 0.14.0",
    "prometheus_client == 0.7.1",
    "PyYAML == 5.1.2",
    "pyaml == 19.4.1",
    "pinject == 0.14.1",
    "decorator < 5.0.0",  # 5.0.0 and later drops py2 support (transitive dep from pinject)
    "six >= 1.12.0",
    "dnspython == 1.16.0",
    "k8s == 0.21.4",
    "appdirs == 1.4.3",
    "requests-toolbelt == 0.9.1",
    "backoff == 1.8.0",
    "py27hash == 1.1.0",
]

WEB_REQ = [
    # TODO: upgrade flask and associated dependencies to 2.x
    "Flask == 1.1.1",
    "flask-talisman==0.7.0",
    "jinja2 <= 2.11.3",  # jinja 3.x requires also upgrading flask to 2.x
    "markupsafe <= 1.1.1",  # markupsafe 2.x requires also upgrading flask to 2.x
    "itsdangerous <= 1.1.0",  # markupsafe 2.x requires also upgrading flask to 2.x
    "werkzeug <= 1.0.1",  # markupsafe 2.x requires also upgrading flask to 2.x
    "blinker == 1.4",
]

DEPLOY_REQ = [
    "requests == 2.27.1",
    "ipaddress == 1.0.22",  # Required by requests for resolving IP address in SSL cert
]

FLAKE8_REQ = [
    "flake8-print == 3.1.4",
    "flake8-comprehensions == 1.4.1",
    "pep8-naming == 0.11.1",
    "flake8 == 3.9.0",
]

TESTS_REQ = [
    "pytest-xdist == 1.27.0",
    "pytest-sugar == 0.9.2",
    "pytest-html == 1.22.0",
    "pytest-cov == 2.7.1",
    "pytest-helpers-namespace == 2019.1.8",
    "pytest == 3.10.1",
    "requests-file == 1.4.3",
    "callee == 0.3",
]

DEV_TOOLS = [
    "tox==3.14.5",
    "virtualenv==20.13.0",
    "black ~= 22.0",
]


if __name__ == "__main__":
    setup(
        name="fiaas-deploy-daemon",
        author="FINN Team Infrastructure",
        author_email="FINN-TechteamInfrastruktur@finn.no",
        version="1.0",
        packages=find_packages(exclude=("tests",)),
        zip_safe=True,
        include_package_data=True,
        # Requirements
        install_requires=GENERIC_REQ + WEB_REQ + DEPLOY_REQ,
        setup_requires=["pytest-runner", "wheel", "setuptools_git >= 0.3"],
        extras_require={
            "dev": TESTS_REQ + FLAKE8_REQ + DEV_TOOLS,
            "ci": DEV_TOOLS,
        },
        # Metadata
        description="Deploy applications to Kubernetes",
        long_description=read("README.md"),
        url="https://github.schibsted.io/finn/fiaas-deploy-daemon",
        # Entrypoints
        entry_points={
            "console_scripts": [
                "fiaas-deploy-daemon = fiaas_deploy_daemon:main",
                "fiaas-deploy-daemon-bootstrap = fiaas_deploy_daemon.bootstrap:main",
            ]
        },
    )
