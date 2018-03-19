from __future__ import print_function


from datetime import datetime
from distutils.version import StrictVersion
import sys
import time
import traceback
from urlparse import urljoin

from monotonic import monotonic as time_monotonic
import requests

from fiaas_deploy_daemon.crd.types import FiaasApplication, FiaasStatus
from fiaas_deploy_daemon.tpr.types import PaasbetaApplication, PaasbetaStatus


def plog(message):
    """Primitive logging"""
    print("%s: %s" % (time.asctime(), message), file=sys.stderr)  # noqa: T001


def wait_until(action, description=None, exception_class=AssertionError, patience=30):
    """Attempt to call 'action' every 2 seconds, until it completes without exception or patience runs out"""
    __tracebackhide__ = True

    start = time_monotonic()
    cause = []
    if not description:
        description = action.__doc__ or action.__name__
    message = []
    while time_monotonic() < (start + patience):
        try:
            action()
            return
        except BaseException:
            cause = traceback.format_exception(*sys.exc_info())
        time.sleep(2)
    if cause:
        message.append("\nThe last exception was:\n")
        message.extend(cause)
    header = "Gave up waiting for {} after {} seconds at {}".format(description, patience, datetime.now().isoformat(" "))
    message.insert(0, header)
    raise exception_class("".join(message))


def tpr_available(kubernetes, timeout=5):
    app_url = urljoin(kubernetes["server"], PaasbetaApplication._meta.url_template.format(namespace="default", name=""))
    status_url = urljoin(kubernetes["server"], PaasbetaStatus._meta.url_template.format(namespace="default", name=""))
    session = requests.Session()
    session.verify = kubernetes["api-cert"]
    session.cert = (kubernetes["client-cert"], kubernetes["client-key"])

    def _tpr_available():
        plog("Checking if TPRs are available")
        for url in (app_url, status_url):
            plog("Checking %s" % url)
            resp = session.get(url, timeout=timeout)
            resp.raise_for_status()
            plog("!!!!! %s is available !!!!" % url)

    return _tpr_available


def crd_available(kubernetes, timeout=5):
    app_url = urljoin(kubernetes["server"], FiaasApplication._meta.url_template.format(namespace="default", name=""))
    status_url = urljoin(kubernetes["server"], FiaasStatus._meta.url_template.format(namespace="default", name=""))
    session = requests.Session()
    session.verify = kubernetes["api-cert"]
    session.cert = (kubernetes["client-cert"], kubernetes["client-key"])

    def _crd_available():
        plog("Checking if CRDs are available")
        for url in (app_url, status_url):
            plog("Checking %s" % url)
            resp = session.get(url, timeout=timeout)
            resp.raise_for_status()
            plog("!!!!! %s is available !!!!" % url)

    return _crd_available


def tpr_supported(k8s_version):
    return StrictVersion("1.6.0") <= StrictVersion(k8s_version[1:]) < StrictVersion("1.8.0")


def crd_supported(k8s_version):
    return StrictVersion("1.7.0") <= StrictVersion(k8s_version[1:])
