#!/usr/bin/env python
# -*- coding: utf-8

# Copyright 2017-2019 The FIAAS Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import logging

from prometheus_client import Counter

LOG = logging.getLogger(__name__)


class SpecFactory(object):
    def __init__(self, factory, transformers, config):
        self._factory = factory
        self._transformers = transformers
        self._config = config
        self._supported_versions = [factory.version] + list(transformers.keys())
        self._fiaas_counter = Counter("fiaas_yml_version", "The version of fiaas.yml used", ["version", "app_name"])

    def __call__(self, uid, name, image, app_config, teams, tags, deployment_id, namespace,
                 additional_labels, additional_annotations):
        """Create an app_spec from app_config"""
        fiaas_version = app_config.get("version", 1)
        self._fiaas_counter.labels(fiaas_version, name).inc()
        LOG.info("Attempting to create app_spec for %s from fiaas.yml version %s", name, fiaas_version)
        try:
            app_config = self.transform(app_config)
            app_spec = self._factory(uid, name, image, teams, tags, app_config, deployment_id, namespace,
                                     additional_labels, additional_annotations)
        except InvalidConfiguration:
            raise
        except Exception as e:
            raise InvalidConfiguration("Failed to parse configuration: {!s}".format(e))
        self._validate(app_spec)
        return app_spec

    def transform(self, app_config, strip_defaults=False):
        fiaas_version = app_config.get("version", 1)
        if fiaas_version not in self._supported_versions:
            raise InvalidConfiguration("Requested version %s, but the only supported versions are: %r" %
                                       (fiaas_version, self._supported_versions))
        current_version = fiaas_version
        while current_version < self._factory.version:
            app_config = self._transformers[current_version](app_config, strip_defaults=strip_defaults)
            current_version = app_config.get("version", 1)
        return app_config

    def _validate(self, app_spec):
        if app_spec.datadog.enabled and self._config.datadog_container_image is None:
            raise InvalidConfiguration("Requested datadog sidecar, but datadog-container-image is undefined")


class BaseFactory(object):
    @property
    def version(self):
        raise NotImplementedError("Subclass must override version property")

    def __call__(self, name, image, teams, tags, app_config, deployment_id, namespace,
                 additional_labels, additional_annotations):
        raise NotImplementedError("Subclass must override __call__")


class BaseTransformer(object):
    def __call__(self, app_config):
        raise NotImplementedError("Subclass must override __call__")


class InvalidConfiguration(Exception):
    pass
