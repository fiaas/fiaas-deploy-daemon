#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import logging
import pkgutil

import pinject
import re

import yaml
from flask import Flask, Blueprint, current_app,  render_template, make_response, request_started, request_finished, \
    got_request_exception, abort, request
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter, Histogram

from ..specs.factory import InvalidConfiguration
from .platform_collector import PLATFORM_COLLECTOR
from .transformer import Transformer

"""Web app that provides metrics and other ways to inspect the action.
Also, endpoints to manually generate AppSpecs and send to deployer for when no pipeline exists.
"""

PLATFORM_COLLECTOR.collect()
LOG = logging.getLogger(__name__)
SPLITTER = re.compile(ur"\s*,\s*")
DEFAULT_NAMESPACE = u"default"

web = Blueprint("web", __name__, template_folder="templates")

request_histogram = Histogram("web_request_latency", "Request latency in seconds", ["page"])
defaults_histogram = request_histogram.labels("defaults")
defaults_versioned_histogram = request_histogram.labels("defaults_versioned")
frontpage_histogram = request_histogram.labels("frontpage")
metrics_histogram = request_histogram.labels("metrics")
transform_histogram = request_histogram.labels("transform")
healthz_histogram = request_histogram.labels("healthz")


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
@defaults_histogram.time()
def defaults():
    return _render_defaults("fiaas_deploy_daemon.specs.v3", "defaults.yml")


@web.route("/defaults/<int:version>")
@defaults_versioned_histogram.time()
def defaults_versioned(version):
    return _render_defaults("fiaas_deploy_daemon.specs.v{}".format(version), "defaults.yml")


@web.route("/healthz")
@healthz_histogram.time()
def healthz():
    if current_app.health_check.is_healthy():
        return "OK", 200
    else:
        return "I don't feel so good...", 500


@web.route("/transform", methods=['GET', 'POST'])
@transform_histogram.time()
def transform():
    if request.method == 'GET':
        return render_template("transform.html")
    elif request.method == 'POST':
        return _transform(yaml.safe_load(request.get_data()))


def _transform(app_config):
    try:
        data = current_app.transformer.transform(app_config)
        return current_app.response_class(data, content_type='text/vnd.yaml; charset=utf-8')
    except InvalidConfiguration as err:
        abort(400, err.message)


def _connect_signals():
    rs_counter = Counter("web_request_started", "HTTP requests received")
    request_started.connect(lambda s, *a, **e: rs_counter.inc(), weak=False)
    rf_counter = Counter("web_request_finished", "HTTP requests successfully handled")
    request_finished.connect(lambda s, *a, **e: rf_counter.inc(), weak=False)
    re_counter = Counter("web_request_exception", "Failed HTTP requests")
    got_request_exception.connect(lambda s, *a, **e: re_counter.inc(), weak=False)


def _render_defaults(*args):
    data = pkgutil.get_data(*args)
    if data:
        resp = make_response(data)
        resp.mimetype = "text/vnd.yaml; charset=utf-8"
        return resp
    else:
        abort(404)


class WebBindings(pinject.BindingSpec):
    def provide_webapp(self, deploy_queue, config, spec_factory, health_check, app_config_downloader):
        app = Flask(__name__)
        app.health_check = health_check
        app.register_blueprint(web)
        app.spec_factory = spec_factory
        app.transformer = Transformer(spec_factory)
        _connect_signals()
        return app
