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
from __future__ import absolute_import, unicode_literals, print_function

import base64
import logging
import socket
from collections import namedtuple

import dns.resolver
import six
from k8s import config
from k8s.base import Model
from k8s.client import NotFound
from k8s.fields import Field
from k8s.models.common import ObjectMeta
from k8s.models.ingress import Ingress
from requests.packages.urllib3.contrib import pyopenssl as reqs

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(it, *args, **kwargs):
        return it


logging.basicConfig(level=logging.INFO, format="%(message)s")

LOG = logging.getLogger()

PROD02_ADDRS = [a.address for a in dns.resolver.query("ingress.prod02.cre-pro.schibsted.io")]


class Secret(Model):
    class Meta:
        list_url = "/api/v1/secrets"
        url_template = "/api/v1/namespaces/{namespace}/secrets/{name}"

    metadata = Field(ObjectMeta)
    data = Field(dict)
    type = Field(six.text_type)


class ProblemType:
    TOO_LONG = 1
    WRONG_DNS = 2
    UNKNOWN_HOST = 3
    WRONG_CA = 4
    NO_CERTIFICATE = 5
    OTHER = 99


Problem = namedtuple("Problem", ("host", "reason", "type"))
Report = namedtuple("Report", ("ingress", "problems"))


def _host_unreachable(host):
    """Check that the host is defined in DNS and points to the common ingress controller"""
    try:
        hostname, aliaslist, addrlist = socket.gethostbyname_ex(host)
        if not all(addr in PROD02_ADDRS for addr in addrlist):
            return Problem(host, "DNS does not point to prod02 ingress", ProblemType.WRONG_DNS)
    except socket.gaierror as e:
        return Problem(host, str(e), ProblemType.UNKNOWN_HOST)
    return None


def _has_ingress_white_list(ingress):
    """Check if the ingress has whitelisting applied"""
    return bool(ingress.metadata.annotations.get("ingress.kubernetes.io/whitelist-source-range", False))


def _has_selected_ingress_class(ingress):
    """Check if a non-default ingress class has been selected"""
    return _get_ingress_class(ingress) is not None


def _get_certificate_issuer_cn(secret):
    crt = base64.b64decode(secret.data["tls.crt"])
    x509 = reqs.OpenSSL.crypto.load_certificate(
        reqs.OpenSSL.crypto.FILETYPE_PEM,
        crt
    )
    issuer = x509.get_issuer()
    return issuer.CN


def _has_invalid_certificate(ingress):
    """Check if any of the certificates for an ingress are invalid"""
    invalid_certs = []
    for certificate_request in ingress.spec.tls:
        secret_name = certificate_request.secretName
        try:
            secret = Secret.get(secret_name, ingress.metadata.namespace)
            issuer_cn = _get_certificate_issuer_cn(secret)
            if "Let's Encrypt Authority X3" != issuer_cn:
                invalid_certs.append(Problem(secret_name, "Incorrect issuer: {}".format(issuer_cn),
                                             ProblemType.WRONG_CA))
        except NotFound:
            invalid_certs.append(Problem(secret_name, "No certificate provisioned", ProblemType.NO_CERTIFICATE))
    return invalid_certs


def _get_ingress_class(ingress):
    return ingress.metadata.annotations.get("kubernetes.io/ingress.class", None)


def _get_unreachable_hosts(ingress):
    unreachable = []
    for certificate_request in ingress.spec.tls:
        for host in certificate_request.hosts:
            unreachable.append(_host_unreachable(host))
    return [u for u in unreachable if u is not None]


def _get_ingresses():
    # The find method doesn't allow the query we need, so we do it outside
    resp = Ingress._client.get(Ingress._meta.list_url, params={"labelSelector": "fiaas/deployed_by"})
    all_ingresses = [Ingress.from_dict(item) for item in resp.json()["items"]]
    tls_ingresses = [ing for ing in all_ingresses if ing.spec.tls]
    return tls_ingresses


def _write_report(needs_certificate, reports):
    LOG.info("h3. Ingresses with problems\n\n")
    needs_fixing = 0
    for report in reports:
        if all(p.type in (ProblemType.TOO_LONG, ProblemType.NO_CERTIFICATE) for p in report.problems):
            continue
        needs_fixing += 1
        LOG.info("h4. {}\n\n".format(report.ingress))
        for problem in report.problems:
            LOG.info("* {}: {}".format(problem.host, problem.reason))
        LOG.info("")
    LOG.info("h3. {} ingresses needs certificates, {} ingresses must be fixed".format(needs_certificate, needs_fixing))


def _collect_problems(ingresses):
    needs_certificate = 0
    reports = []
    for ingress in tqdm(ingresses, desc="Analyzing Ingresses"):
        invalid_certificates = _has_invalid_certificate(ingress)
        unreachable_hosts = _get_unreachable_hosts(ingress)
        if not (invalid_certificates or unreachable_hosts):
            continue
        needs_certificate += 1
        problems = []
        if invalid_certificates:
            for ic in invalid_certificates:
                if len(ic.host) > 63:
                    problems.append(ic._replace(
                        reason="Host is too long ({}) to be a CommonName".format(len(ic.host)),
                        type=ProblemType.TOO_LONG))
                else:
                    problems.append(ic)
        if unreachable_hosts:
            for uh in unreachable_hosts:
                problems.append(uh)
        if problems:
            reports.append(Report("{}/{}".format(ingress.metadata.namespace, ingress.metadata.name), problems))
    return needs_certificate, reports


def main():
    config.api_server = "http://localhost:8001"  # Assume running `kubectl proxy`
    socket.setdefaulttimeout(5.0)
    ingresses = _get_ingresses()
    needs_certificate, reports = _collect_problems(ingresses)
    _write_report(needs_certificate, reports)


if __name__ == "__main__":
    main()
