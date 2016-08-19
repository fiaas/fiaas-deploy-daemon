#!/usr/bin/env python
# -*- coding: utf-8
from fiaas_deploy_daemon.specs import models


class TestSpecs(object):
    def test_version_property(self):
        app_spec = models.AppSpec(None, u"test", u"test/image:version", None, 1, None, None, None, None)
        assert app_spec.version == u"version"

    def test_unknown_version(self):
        app_spec = models.AppSpec(None, u"test", u"test/image", None, 1, None, None, None, None)
        assert app_spec.version == u"<unknown>"

    def test_service_name(self):
        service_spec = models.ServiceSpec(1234, 5678, u"type")
        assert service_spec.name == u"type1234"
