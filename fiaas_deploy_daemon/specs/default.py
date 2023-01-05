import logging

LOG = logging.getLogger(__name__)


class DefaultAppSpec(object):
    DEFAULT_APP_CONFIG = {
        "version": 3,
    }

    def __init__(self, spec_factory):
        self.default_app_spec = spec_factory(
            None, None, None, self.DEFAULT_APP_CONFIG, None, None, None, None, None, None
        )

    def __call__(self, *args, **kwargs):
        return self.default_app_spec
