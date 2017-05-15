#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

from prometheus_client import Counter


class SpecFactory(object):
    def __init__(self, factories):
        self._factories = factories
        self._fiaas_counter = Counter("fiaas_yml_version", "The version of fiaas.yml used", ["version"])

    def __call__(self, name, image, app_config, teams, tags):
        """Create an app_spec from app_config"""
        fiaas_version = app_config.get(u"version", 1)
        self._fiaas_counter.labels(fiaas_version).inc()
        factory = self._factories[fiaas_version]
        return factory(name, image, teams, tags, app_config)
