#!/usr/bin/env python
# -*- coding: utf-8

from __future__ import unicode_literals, absolute_import

import pytest

from fiaas_deploy_daemon.secrets import resolve_secrets

KEY = "TRACKING_KEY"


class TestSecrets(object):
    @pytest.fixture
    def secrets_dir(self, tmpdir_factory):
        yield tmpdir_factory.mktemp("secrets", numbered=True)

    def test_reads_files(self, secrets_dir):
        secrets_dir.join("tracking_key").write(KEY)
        secrets = resolve_secrets(str(secrets_dir))
        assert secrets.tracking_key == KEY

    def test_ignores_missing_files(self, secrets_dir):
        secrets = resolve_secrets(str(secrets_dir))
        assert secrets.tracking_key is None

    def test_ignores_extra_files(self, secrets_dir):
        secrets_dir.join("ignore_me").write("ignored")
        resolve_secrets(str(secrets_dir))
