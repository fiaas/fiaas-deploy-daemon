#!/usr/bin/env python
# -*- coding: utf-8

import pytest
import yaml


@pytest.fixture
def load_app_config_testdata(request):
    def _load(filename):
        path = _find_file(filename+".yml", request.fspath.dirpath())
        with open(path, 'r') as fobj:
            return yaml.safe_load(fobj)
    return _load


def _find_file(needle, root):
    parents = root.parts(True)
    for parent in parents:
        candidate = parent.join(needle)
        if candidate.check():
            return candidate.strpath
        candidate = parent.join("data", needle)
        if candidate.check():
            return candidate.strpath
    raise ValueError("File {} not found".format(needle))
