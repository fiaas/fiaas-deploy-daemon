
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

import yaml


class AppConfigDownloader(object):
    def __init__(self, session, timeout_seconds=10):
        self._session = session
        self._timeout_seconds = timeout_seconds

    def get(self, fiaas_url):
        resp = self._session.get(fiaas_url, timeout=self._timeout_seconds)
        resp.raise_for_status()
        app_config = yaml.safe_load(resp.text)
        return app_config
