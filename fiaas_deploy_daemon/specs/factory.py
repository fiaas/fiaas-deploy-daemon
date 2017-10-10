#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import logging

from prometheus_client import Counter

LOG = logging.getLogger(__name__)


class SpecFactory(object):
    def __init__(self, factory, transformers):
        self._factory = factory
        self._transformers = transformers
        self._supported_versions = [factory.version] + transformers.keys()
        self._fiaas_counter = Counter("fiaas_yml_version", "The version of fiaas.yml used", ["version"])

    def __call__(self, name, image, app_config, teams, tags, deployment_id):
        """Create an app_spec from app_config"""
        fiaas_version = app_config.get(u"version", 1)
        self._fiaas_counter.labels(fiaas_version).inc()
        LOG.info("Attempting to create app_spec for %s from fiaas.yml version %s", name, fiaas_version)
        if fiaas_version not in self._supported_versions:
            raise InvalidConfiguration("Requested version %s, but the only supported versions are: %r" %
                                       (fiaas_version, self._supported_versions))
        app_config = self._transform(app_config)
        return self._factory(name, image, teams, tags, app_config, deployment_id)

    def _transform(self, app_config):
        current_version = app_config.get(u"version", 1)
        while current_version < self._factory.version:
            app_config = self._transformers[current_version](app_config)
            current_version = app_config.get(u"version", 1)
        return app_config


class BaseFactory(object):
    @property
    def version(self):
        raise NotImplementedError("Subclass must override version property")

    def __call__(self, name, image, teams, tags, app_config, deployment_id):
        raise NotImplementedError("Subclass must override __call__")


class BaseTransformer(object):
    @property
    def version(self):
        raise NotImplementedError("Subclass must override version property")

    def __call__(self, app_config):
        raise NotImplementedError("Subclass must override __call__")


class InvalidConfiguration(Exception):
    pass
