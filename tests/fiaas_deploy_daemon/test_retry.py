from requests import Response
from k8s.client import ClientError
import mock
import pytest

from fiaas_deploy_daemon.retry import retry_on_upsert_conflict, UpsertConflict


@pytest.mark.parametrize("status", (
    400,  # Bad Request
    402,  # Payment Required
    403,  # Forbidden
    404,  # Not Found
    405,  # Method Not Allowed
    406,  # Not Acceptable
    408,  # Request Timeout
    410,  # Gone
    411,  # Length Required
    413,  # Payload Too Large
    414,  # URI Too long
    415,  # Unsupported Media Type
    417,  # Expectation Failed
    426,  # Upgrade Required
))
def test_retry_on_conflict_should_raise_clienterror_for_non_conflict_clienterror(status):
    response = mock.MagicMock(spec=Response)
    response.status_code = status

    @retry_on_upsert_conflict
    def fail():
        raise ClientError("No", response=response)

    with pytest.raises(ClientError):
        fail()


def test_retry_on_conflict_should_raise_upsertconflict_for_conflict():
    response = mock.MagicMock(spec=Response)
    response.status_code = 409  # Conflict

    @retry_on_upsert_conflict(max_value=0.001, max_tries=1)
    def fail():
        raise ClientError("No", response=response)

    with pytest.raises(UpsertConflict):
        fail()


def test_retry_on_conflict_should_retry_on_conflict():
    response = mock.MagicMock(spec=Response)
    response.status_code = 409  # Conflict
    max_tries = 3
    global calls
    calls = 0

    @retry_on_upsert_conflict(max_value=0.001, max_tries=max_tries)
    def fail():
        global calls
        calls += 1
        raise ClientError(response=response)

    with pytest.raises(UpsertConflict):
        fail()

    assert calls == max_tries


def test_retry_on_conflict_calls_decorated_function_and_returns_return_value():
    expected = object()
    max_tries = 1
    global calls
    calls = 0

    @retry_on_upsert_conflict(max_value=0.001, max_tries=max_tries)
    def succeed():
        global calls
        calls += 1
        return expected

    assert succeed() == expected
    assert calls == max_tries
