from fiaas_deploy_daemon import HealthCheck
from fiaas_deploy_daemon.specs.factory import SpecFactory

from fiaas_deploy_daemon.web import WebBindings

from unittest import mock

import pkgutil
import pytest


@pytest.fixture
def health_check():
    yield mock.create_autospec(HealthCheck, spec_set=True)


@pytest.fixture()
def spec_factory():
    yield mock.create_autospec(SpecFactory, spec_set=True)


@pytest.fixture
def app(health_check, spec_factory):
    bindings = WebBindings()
    yield bindings.provide_webapp(spec_factory, health_check)


@pytest.fixture()
def client(app):
    return app.test_client()


class TestEndpoints:
    def test_frontpage(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"<p>Welcome to the FIAAS deploy daemon.</p>" in resp.data

    def test_metrics(self, client):
        # because only the web module of the appliction is under test here and other parts are unavailable or mocked,
        # only the metrics defined in that module will be on the response
        expected_metrics = [
            b"web_request_started_total",
            b"web_request_finished_total",
            b"web_request_exception_total",
        ]

        resp = client.get("/internal-backstage/prometheus")

        assert resp.status_code == 200
        for metric_name in expected_metrics:
            assert metric_name in resp.data

    def test_defaults(self, client):
        defaults_raw = pkgutil.get_data("fiaas_deploy_daemon.specs.v3", "defaults.yml")

        resp = client.get("/defaults")

        assert resp.status_code == 200
        assert resp.data == defaults_raw

    @pytest.mark.parametrize("version", ("2", "3"))
    def test_defaults_versioned(self, client, version):
        defaults_raw = pkgutil.get_data(f"fiaas_deploy_daemon.specs.v{version}", "defaults.yml")

        resp = client.get(f"/defaults/{version}")

        assert resp.status_code == 200
        assert resp.data == defaults_raw

    @pytest.mark.parametrize(
        "is_healthy, status_code",
        (
            (True, 200),
            (False, 500),
        ),
    )
    def test_healthcheck(self, client, health_check, is_healthy, status_code):
        health_check.is_healthy.return_value = is_healthy

        resp = client.get("/healthz")
        assert resp.status_code == status_code

    def test_transform_get(self, client):
        resp = client.get("/transform")

        assert resp.status_code == 200
        assert b"<p>Transform fiaas applicaton config.</p>" in resp.data

    def test_transform_post(self, spec_factory, client):
        app_config = "version: 2"
        expected_response = b"version: 3\n"

        spec_factory.transform.return_value = {"version": 3}

        resp = client.post("/transform", data=app_config)

        assert resp.status_code == 200
        assert resp.data == expected_response
