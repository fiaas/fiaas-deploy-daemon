#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import logging
import pkgutil

import pinject
import re
from flask import Flask, Blueprint, current_app, render_template, request, flash, url_for, redirect, make_response, \
    request_started, request_finished, got_request_exception, abort
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter, Histogram

from .forms import DeployForm
from .platform_collector import PLATFORM_COLLECTOR
from ..deployer import DeployerEvent

"""Web app that provides metrics and other ways to inspect the action.
Also, endpoints to manually generate AppSpecs and send to deployer for when no pipeline exists.
"""

PLATFORM_COLLECTOR.collect()
LOG = logging.getLogger(__name__)
SPLITTER = re.compile(ur"\s*,\s*")
DEFAULT_NAMESPACE = u"default"

web = Blueprint("web", __name__, template_folder="templates")
fiaas_counter = Counter("web_fiaas_deploy", "Fiaas App deploy requested through web")

request_histogram = Histogram("web_request_latency", "Request latency in seconds", ["page"])
frontpage_histogram = request_histogram.labels("frontpage")
fiaas_histogram = request_histogram.labels("fiaas")
metrics_histogram = request_histogram.labels("metrics")


@web.route("/")
@frontpage_histogram.time()
def frontpage():
    fiaas = DeployForm(request.form)
    return render_template("frontpage.html",
                           config=current_app.cfg,
                           fiaas=fiaas)


@web.route("/fiaas", methods=["POST"])
@fiaas_histogram.time()
def fiaas():
    form = DeployForm(request.form)
    if form.validate_on_submit():
        fiaas_url = form.fiaas.data
        app_config = current_app.app_config_downloader.get(fiaas_url)
        teams = SPLITTER.split(form.teams.data)
        tags = SPLITTER.split(form.tags.data)

        if app_config["version"] == 2:
            namespace = DEFAULT_NAMESPACE
        elif form.namespace:
            namespace = form.namespace
        else:
            LOG.error("namespace is required if version is not 2")
            abort(400)

        app_spec = current_app.spec_factory(form.name.data, form.image.data, app_config, teams, tags,
                                            form.deployment_id.data, namespace)
        current_app.deploy_queue.put(DeployerEvent("UPDATE", app_spec))
        flash("Deployment request sent...")
        LOG.info("Deployment request sent...")
        fiaas_counter.inc()
        return redirect(url_for("web.frontpage"))
    else:
        LOG.error("Invalid form data")
    return render_template("frontpage.html",
                           config=current_app.cfg,
                           fiaas=form)


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
        require("deploy_queue")
        require("spec_factory")
        require("app_config_downloader")

    def provide_webapp(self, deploy_queue, config, spec_factory, health_check, app_config_downloader):
        app = Flask(__name__)
        app.deploy_queue = deploy_queue
        app.config.from_object(config)
        app.cfg = config
        app.spec_factory = spec_factory
        app.health_check = health_check
        app.app_config_downloader = app_config_downloader
        app.register_blueprint(web)
        _connect_signals()
        return app
