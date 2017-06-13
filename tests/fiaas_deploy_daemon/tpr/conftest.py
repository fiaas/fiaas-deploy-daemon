
import pytest
import mock

from k8s import config


@pytest.fixture(autouse=True)
def k8s_config(monkeypatch):
    """Configure k8s for test-runs"""
    monkeypatch.setattr(config, "api_server", "https://10.0.0.1")
    monkeypatch.setattr(config, "api_token", "password")
    monkeypatch.setattr(config, "verify_ssl", False)


@pytest.fixture(autouse=True)
def get():
    with mock.patch('k8s.client.Client.get') as mockk:
        yield mockk


@pytest.fixture(autouse=True)
def post():
    with mock.patch('k8s.client.Client.post') as mockk:
        yield mockk


@pytest.fixture(autouse=True)
def put():
    with mock.patch('k8s.client.Client.put') as mockk:
        yield mockk


@pytest.fixture(autouse=True)
def delete():
    with mock.patch('k8s.client.Client.delete') as mockk:
        yield mockk
