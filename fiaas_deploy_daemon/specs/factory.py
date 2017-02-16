#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import yaml
from prometheus_client import Counter


class SpecFactory(object):
    def __init__(self, session, factories):
        self._session = session
        self._factories = factories
        self._fiaas_counter = Counter("fiaas_yml_version", "The version of fiaas.yml used", ["version"])

    def __call__(self, name, image, url, teams, tags):
        """Create an app_spec from the fiaas-config at the given URL"""
        resp = self._session.get(url, timeout=10)
        resp.raise_for_status()
        app_config = yaml.safe_load(resp.text)
        fiaas_version = app_config.get(u"version", 1)
        self._fiaas_counter.labels(fiaas_version).inc()
        factory = self._factories[fiaas_version]
        return factory(name, image, teams, tags, app_config)
