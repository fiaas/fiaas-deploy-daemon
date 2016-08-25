#!/usr/bin/env python
# -*- coding: utf-8

import pytest
from requests import Session
from requests_file import FileAdapter


@pytest.fixture
def session():
    session = Session()
    session.mount("file://", FileAdapter())
    return session


@pytest.fixture
def make_url(request):
    def _make(filename):
        path = _find_file(filename+".yml", request.fspath.dirpath())
        return "file://{}".format(path)
    return _make


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
