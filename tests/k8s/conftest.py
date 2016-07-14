#!/usr/bin/env python
# -*- coding: utf-8

import logging

import pytest

from k8s import config


@pytest.yield_fixture
def logger():
    """Set root logger to DEBUG, and add stream handler"""
    root_logger = logging.getLogger()
    old_level = root_logger.getEffectiveLevel()
    root_logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    root_logger.addHandler(handler)
    yield root_logger
    root_logger.removeHandler(handler)
    root_logger.setLevel(old_level)


@pytest.fixture
def k8s_config(monkeypatch):
    """Configure k8s for test-runs"""
    monkeypatch.setattr(config, "api_server", "https://10.0.0.1")
    monkeypatch.setattr(config, "api_token", "password")
    monkeypatch.setattr(config, "verify_ssl", False)
