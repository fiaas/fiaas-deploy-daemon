# Copyright 2017-2019 The FIAAS Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from unittest import mock
import pytest
from k8s.client import ClientError
from requests import Response, Request

from fiaas_deploy_daemon.retry import retry_on_upsert_conflict, UpsertConflict, canonical_name


def test_upsertconflict_str():
    expected = "409 Conflict for POST http://example.com. reason=bad conflict, message=conflict because of reasons"

    response = mock.MagicMock(spec=Response)
    response.status_code = 409  # Conflict
    request = mock.MagicMock(spec=Request)
    request.method = "POST"
    request.url = "http://example.com"
    response.request = request
    response.json.return_value = {"reason": "bad conflict", "message": "conflict because of reasons"}

    e = UpsertConflict(response)

    assert str(e) == expected


@pytest.mark.parametrize(
    "status",
    (
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
    ),
)
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

    @retry_on_upsert_conflict(max_value_seconds=0.001, max_tries=1)
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

    @retry_on_upsert_conflict(max_value_seconds=0.001, max_tries=max_tries)
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

    @retry_on_upsert_conflict
    def succeed():
        global calls
        calls += 1
        return expected

    assert succeed() == expected
    assert calls == max_tries


class NameTester(object):
    @classmethod
    def clsmethod(cls):
        pass

    def method(self):
        pass


def name_test_function():
    pass


@pytest.mark.parametrize(
    "func, expected",
    (
        (id, "builtins.id"),
        (name_test_function, "{}.name_test_function".format(__name__)),
        (NameTester.clsmethod, "{}.NameTester.clsmethod".format(__name__)),
        (NameTester.method, "{}.NameTester.method".format(__name__)),
    ),
)
def test_canonical_name(func, expected):
    assert canonical_name(func) == expected
