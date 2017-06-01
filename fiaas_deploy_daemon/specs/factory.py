#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import logging

from prometheus_client import Counter


LOG = logging.getLogger(__name__)


class SpecFactory(object):
    def __init__(self, factories):
        self._factories = factories
        self._fiaas_counter = Counter("fiaas_yml_version", "The version of fiaas.yml used", ["version"])

    def __call__(self, name, image, app_config, teams, tags, deployment_id):
        """Create an app_spec from app_config"""
        fiaas_version = app_config.get(u"version", 1)
        LOG.info("Creating app_spec for %s from fiaas.yml version %d", name, fiaas_version)
        self._fiaas_counter.labels(fiaas_version).inc()
        factory = self._factories[fiaas_version]
        return factory(name, image, teams, tags, app_config, deployment_id)
