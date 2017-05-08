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
