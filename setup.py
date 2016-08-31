#!/usr/bin/env python
# -*- coding: utf-8

import os
from setuptools import setup, find_packages


def read(filename):
    with open(os.path.join(os.path.dirname(__file__), filename)) as f:
        return f.read()


GENERIC_REQ = [
    "ConfigArgParse == 0.10.0",
    "prometheus_client == 0.0.13",
    "PyYAML == 3.11",
    "pinject == 0.10.2"
]

WEB_REQ = [
    "Flask == 0.10.1",
    "Flask-WTF == 0.12",
    "blinker == 1.4"
]

PIPELINE_REQ = [
    # "kafka == 1.0.2" # TODO: Switch to 1.0.2 when released
    "kafka-python == 0.9.5"
]

DEPLOY_REQ = [
    "requests == 2.9.1",
    "google-api-python-client == 1.5.1",
]

FLAKE8_REQ = [
    'flake8-print',
    'flake8-comprehensions',
    'pep8-naming',
    'flake8'
]

TESTS_REQ = [
    'vcrpy',
    'mock',
    'pytest-sugar',
    'pytest-html',
    'pytest-cov',
    'pytest-helpers-namespace',
    'pytest',
    'requests-file',
]

setup(
        name="fiaas-deploy-daemon",
        author="FINN Team Infrastructure",
        author_email="FINN-TechteamInfrastruktur@finn.no",
        version="1.0",
        packages=find_packages(exclude=("tests",)),
        zip_safe=True,
        include_package_data=True,

        # Requirements
        install_requires=GENERIC_REQ + WEB_REQ + PIPELINE_REQ + DEPLOY_REQ + FLAKE8_REQ,
        setup_requires=['pytest-runner', 'wheel', 'setuptools_git >= 0.3'],
        tests_require=TESTS_REQ,

        # Metadata
        description="Deploy docker containers to kubernetes when notified by pipeline",
        long_description=read("README.md"),
        url="https://git.finn.no/projects/TOOL/repos/fiaas-deploy-daemon",

        # Entrypoints
        entry_points={
            "console_scripts": [
                "fiaas-deploy-daemon = fiaas_deploy_daemon:main",
                "create-dns-with-static-ip = fiaas_deploy_daemon.deployer.gke:create_dns_with_static_ip"
            ]
        }
)
