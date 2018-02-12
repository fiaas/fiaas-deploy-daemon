import pyaml


class Transformer(object):
    def __init__(self, spec_factory):
        self._spec_factory = spec_factory

    def transform(self, app_config):
        converted_app_config = self._spec_factory.transform(app_config, strip_defaults=True)
        return pyaml.dump(converted_app_config)
