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


import pytest

from fiaas_deploy_daemon.secrets import resolve_secrets

KEY = b"USAGE_REPORTING_KEY"


class TestSecrets(object):
    @pytest.fixture
    def secrets_dir(self, tmpdir_factory):
        yield tmpdir_factory.mktemp("secrets", numbered=True)

    def test_reads_files(self, secrets_dir):
        secrets_dir.join("usage-reporting-key").write(KEY)
        secrets = resolve_secrets(str(secrets_dir))
        assert secrets.usage_reporting_key == KEY

    def test_expects_filename_with_underscores_replaced_by_dashes(self, secrets_dir):
        secrets_dir.join("usage_reporting_key").write(KEY)
        secrets = resolve_secrets(str(secrets_dir))
        assert secrets.usage_reporting_key is None

    def test_ignores_missing_files(self, secrets_dir):
        secrets = resolve_secrets(str(secrets_dir))
        assert secrets.usage_reporting_key is None

    def test_ignores_extra_files(self, secrets_dir):
        secrets_dir.join("ignore-me").write("ignored")
        resolve_secrets(str(secrets_dir))

    def test_secrets_are_bytes(self, secrets_dir):
        secrets_dir.join("usage-reporting-key").write(KEY)
        secrets = resolve_secrets(str(secrets_dir))
        assert isinstance(secrets.usage_reporting_key, bytes)

    def test_secrets_are_stripped(self, secrets_dir):
        secrets_dir.join("usage-reporting-key").write(KEY + "\n")
        secrets = resolve_secrets(str(secrets_dir))
        assert secrets.usage_reporting_key == KEY
