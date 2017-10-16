#!/usr/bin/env python
# -*- coding: utf-8

import pytest
import yaml


@pytest.fixture
def load_app_config_testdata(request):
    def _load(filename):
        path = _find_file(filename+".yml", request.fspath.dirpath(), "examples")
        with open(path, 'r') as fobj:
            return yaml.safe_load(fobj)
    return _load


@pytest.fixture
def load_app_config_transformations(request):
    def _load(filename):
        path = _find_file(filename+".yml", request.fspath.dirpath(), "transformations")
        with open(path, 'r') as fobj:
            return yaml.safe_load(fobj)
    return _load


def _find_file(needle, root, kind):
    parents = root.parts(True)
    for parent in parents:
        dirs = [parent]
        for part in ("data", kind):
            dirs.append(dirs[-1].join(part))
        for d in dirs:
            candidate = d.join(needle)
            if candidate.check():
                return candidate.strpath

    raise ValueError("File {} not found".format(needle))
