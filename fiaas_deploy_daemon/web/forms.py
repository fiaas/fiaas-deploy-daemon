#!/usr/bin/env python
# -*- coding: utf-8

from flask_wtf import FlaskForm
from wtforms.fields import StringField
from wtforms.fields.html5 import URLField
from wtforms.validators import InputRequired, URL


class DeployForm(FlaskForm):
    name = StringField(u"Application name", [InputRequired()])
    image = StringField(u"Docker image reference", [InputRequired()])
    fiaas = URLField(u"URL to FIAAS-config", [InputRequired(), URL(require_tld=False)])
    teams = StringField(u"Teams to label pods with (comma separated)", [InputRequired()])
    tags = StringField(u"Tags to label pods with (comma separated)", [InputRequired()])
    deployment_id = StringField(u"Deployment identifier", [InputRequired()])
