#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import logging
import pkgutil

import pinject
import re
from flask import Flask, Blueprint, current_app,  render_template, make_response, request_started, request_finished, \
    got_request_exception
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter, Histogram

from .platform_collector import PLATFORM_COLLECTOR

"""Web app that provides metrics and other ways to inspect the action.
Also, endpoints to manually generate AppSpecs and send to deployer for when no pipeline exists.
"""

PLATFORM_COLLECTOR.collect()
LOG = logging.getLogger(__name__)
SPLITTER = re.compile(ur"\s*,\s*")
DEFAULT_NAMESPACE = u"default"

web = Blueprint("web", __name__, template_folder="templates")

request_histogram = Histogram("web_request_latency", "Request latency in seconds", ["page"])
frontpage_histogram = request_histogram.labels("frontpage")
metrics_histogram = request_histogram.labels("metrics")


@web.route("/")
@frontpage_histogram.time()
def frontpage():
    return render_template("frontpage.html")


@web.route("/internal-backstage/prometheus")
@metrics_histogram.time()
def metrics():
    resp = make_response(generate_latest())
    resp.mimetype = CONTENT_TYPE_LATEST
    return resp


@web.route("/defaults")
def defaults():
    resp = make_response(pkgutil.get_data("fiaas_deploy_daemon.specs.v2", "defaults.yml"))
    resp.mimetype = "text/vnd.yaml; charset=utf-8"
    return resp


@web.route("/healthz")
def healthz():
    if current_app.health_check.is_healthy():
        return "OK", 200
    else:
        return "I don't feel so good...", 500


def _connect_signals():
    rs_counter = Counter("web_request_started", "HTTP requests received")
    request_started.connect(lambda s, *a, **e: rs_counter.inc(), weak=False)
    rf_counter = Counter("web_request_finished", "HTTP requests successfully handled")
    request_finished.connect(lambda s, *a, **e: rf_counter.inc(), weak=False)
    re_counter = Counter("web_request_exception", "Failed HTTP requests")
    got_request_exception.connect(lambda s, *a, **e: re_counter.inc(), weak=False)


class WebBindings(pinject.BindingSpec):
    def configure(self, require):
        require("config")

    def provide_webapp(self, deploy_queue, config, spec_factory, health_check, app_config_downloader):
        app = Flask(__name__)
        app.config.from_object(config)
        app.health_check = health_check
        app.register_blueprint(web)
        _connect_signals()
        return app
