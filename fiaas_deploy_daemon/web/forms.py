#!/usr/bin/env python
# -*- coding: utf-8

from flask_wtf import Form
from wtforms.fields import StringField, IntegerField, RadioField
from wtforms.fields.html5 import URLField
from wtforms.validators import InputRequired, URL, Optional


class DeployForm(Form):
    name = StringField(u"Application name", [InputRequired()])
    image = StringField(u"Docker image reference", [InputRequired()])


class FiaasForm(DeployForm):
    fiaas = URLField(u"URL to FIAAS-config", [InputRequired(), URL()])

    def __init__(self, formdata):
        super(FiaasForm, self).__init__(formdata, prefix="fiaas")


class ManualForm(DeployForm):
    replicas = IntegerField(u"Number of replicas", [Optional()], default="1")
    type = RadioField(u"Type of service", [InputRequired()], choices=[("http", "http"), ("thrift", "thrift")])
    exposed_port = IntegerField(u"Port exposed in the container", [InputRequired()])
    service_port = IntegerField(u"Port for service", [InputRequired()])
    ingress = StringField(u"Root path for HTTP app", [Optional()], default="/")
    readiness = StringField(u"Path to use for readiness probe", [Optional()], default="/")
    liveness = StringField(u"Path to use for liveness probe", [Optional()], default="/")
    requests_cpu = StringField(u"Request CPU", [Optional()], default=None)
    requests_memory = StringField(u"Request memory", [Optional()], default=None)
    limits_cpu = StringField(u"Limit CPU", [Optional()], default=None)
    limits_memory = StringField(u"Limit memory", [Optional()], default=None)

    def __init__(self, formdata):
        super(ManualForm, self).__init__(formdata, prefix="manual")
