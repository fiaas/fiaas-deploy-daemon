#!/usr/bin/env python
# -*- coding: utf-8

import os

from setuptools import setup, find_packages


def read(filename):
    with open(os.path.join(os.path.dirname(__file__), filename)) as f:
        return f.read()


GENERIC_REQ = [
    "ConfigArgParse == 0.12.0",
    "prometheus_client == 0.3.1",
    "PyYAML == 3.12",
    "pyaml == 16.12.2",
    "pinject == 0.10.2",
    "six == 1.10.0",
    "dnspython == 1.15.0",
    "k8s == 0.11.0",
    "monotonic == 1.3",
    "appdirs == 1.4.3",
    "requests-toolbelt == 0.8.0",
    "backoff == 1.6",
]

WEB_REQ = [
    "Flask == 0.12",
    "flask-talisman==0.5.1",
    "blinker == 1.4",
]

PIPELINE_REQ = [
    # "kafka == 1.0.2" # TODO: Switch to 1.0.2 when released
    "kafka-python == 0.9.5"
]

DEPLOY_REQ = [
    "requests == 2.13.0",
    "ipaddress == 1.0.18"  # Required by requests for resolving IP address in SSL cert
]

FLAKE8_REQ = [
    'flake8-print == 3.1.0',
    'flake8-comprehensions == 1.4.1',
    'pep8-naming == 0.7.0',
    'flake8 == 3.6.0'
]

TESTS_REQ = [
    'mock == 2.0.0',
    'pytest-xdist == 1.25.0',
    'pytest-sugar == 0.9.2',
    'pytest-html == 1.19.0',
    'pytest-cov == 2.6.0',
    'pytest-helpers-namespace == 2017.11.11',
    'pytest == 3.10.1',
    'requests-file == 1.4.3',
    'callee == 0.3',
]

DEV_TOOLS = [
    "tox==3.6.1",
]

# Transient dependencies that needs to be pinned for various reasons
TRANSIENT_PINNED_TEST_REQ = [
    "coverage==4.5.1",  # For some reason we end up pulling a buggy pre-release version without this
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
        install_requires=GENERIC_REQ + WEB_REQ + PIPELINE_REQ + DEPLOY_REQ,
        setup_requires=['pytest-runner', 'wheel', 'setuptools_git >= 0.3'],
        extras_require={
            "dev": TESTS_REQ + TRANSIENT_PINNED_TEST_REQ + FLAKE8_REQ + DEV_TOOLS
        },

        # Metadata
        description="Deploy docker containers to kubernetes when notified by pipeline",
        long_description=read("README.md"),
        url="https://github.schibsted.io/finn/fiaas-deploy-daemon",

        # Entrypoints
        entry_points={
            "console_scripts": [
                "fiaas-deploy-daemon = fiaas_deploy_daemon:main",
                "fiaas-deploy-daemon-bootstrap = fiaas_deploy_daemon.bootstrap:main",
            ]
        }
    )
