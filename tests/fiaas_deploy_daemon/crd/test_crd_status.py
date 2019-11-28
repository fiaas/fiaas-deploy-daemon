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

import random
import re
from collections import namedtuple

import mock
import pytest
from blinker import Namespace
from k8s.client import ClientError, NotFound
from k8s.models.common import ObjectMeta
from requests import Response

from fiaas_deploy_daemon.crd import status
from fiaas_deploy_daemon.crd.status import _cleanup, OLD_STATUSES_TO_KEEP, LAST_UPDATED_KEY, now
from fiaas_deploy_daemon.crd.types import FiaasApplicationStatus
from fiaas_deploy_daemon.lifecycle import DEPLOY_STATUS_CHANGED, STATUS_INITIATED, STATUS_STARTED, STATUS_SUCCESS, STATUS_FAILED
from fiaas_deploy_daemon.retry import UpsertConflict, CONFLICT_MAX_RETRIES
from fiaas_deploy_daemon.tools import merge_dicts
from fiaas_deploy_daemon.lifecycle import Subject
from utils import configure_mock_fail_then_success

LAST_UPDATE = now()
LOG_LINE = "This is a log line from a test."
DEPLOYMENT_ID = u"deployment_id"
NAME = u"name"
VALID_NAME = re.compile(r"^[a-z0-9.-]+$")


class TestStatusReport(object):
    @pytest.fixture
    def get_or_create(self):
        with mock.patch("fiaas_deploy_daemon.crd.status.FiaasApplicationStatus.get_or_create", spec_set=True) as m:
            yield m

    @pytest.fixture
    def find(self):
        with mock.patch("fiaas_deploy_daemon.crd.status.FiaasApplicationStatus.find", spec_set=True) as m:
            m.return_value = []
            yield m

    @pytest.fixture
    def delete(self):
        with mock.patch("fiaas_deploy_daemon.crd.status.FiaasApplicationStatus.delete", spec_set=True) as m:
            yield m

    @pytest.fixture
    def signal(self, monkeypatch):
        s = Namespace().signal
        monkeypatch.setattr("fiaas_deploy_daemon.crd.status.signal", s)
        yield s

    @pytest.fixture
    def logs(self):
        with mock.patch("fiaas_deploy_daemon.crd.status._get_logs") as m:
            m.return_value = [LOG_LINE]
            yield m

    @pytest.fixture
    def save(self):
        with mock.patch("fiaas_deploy_daemon.crd.status.FiaasApplicationStatus.save", spec_set=True) as m:
            yield m

    # create vs update => new_status, url, post/put
    def pytest_generate_tests(self, metafunc):
        if metafunc.cls == self.__class__ and "test_data" in metafunc.fixturenames:
            TestData = namedtuple("TestData", ("signal_name", "action", "status", "result", "new",
                                               "called_mock", "ignored_mock"))
            name2result = {
                STATUS_STARTED: u"RUNNING",
                STATUS_FAILED: u"FAILED",
                STATUS_SUCCESS: u"SUCCESS",
                STATUS_INITIATED: u"INITIATED"
            }
            action2data = {
                "create": (True, "post", "put"),
                "update": (False, "put", "post")
            }
            for result in (STATUS_STARTED, STATUS_FAILED, STATUS_SUCCESS, STATUS_INITIATED):
                for action in ("create", "update"):

                    test_data = TestData(DEPLOY_STATUS_CHANGED, action, result, name2result[result], *action2data[action])
                    test_id = "{} status on {}".format(action, result)
                    metafunc.addcall({"test_data": test_data}, test_id)

    @pytest.mark.usefixtures("post", "put", "find", "logs")
    def test_action_on_signal(self, request, get, app_spec, test_data, signal):
        app_name = '{}-isb5oqum36ylo'.format(test_data.result)
        expected_logs = [LOG_LINE]
        if not test_data.new:
            get.side_effect = lambda *args, **kwargs: mock.DEFAULT  # disable default behavior of raising NotFound
            get_response = mock.create_autospec(Response)
            get_response.json.return_value = {
                'apiVersion': 'fiaas.schibsted.io/v1',
                'kind': 'ApplicationStatus',
                'metadata': {
                    'labels': {
                        'app': app_spec.name,
                        'fiaas/deployment_id': app_spec.deployment_id,
                    },
                    'annotations': {
                        'fiaas/last_updated': LAST_UPDATE,
                    },
                    'namespace': 'default',
                    'name': app_name,
                    },
                'result': 'INITIATED',
                'logs': expected_logs,
            }
            get.return_value = get_response

        # expected data used in expected api response and to configure mocks
        labels = app_spec.labels._replace(status={"status/label": "true"})
        annotations = app_spec.annotations._replace(status={"status/annotations": "true"})
        app_spec = app_spec._replace(name=test_data.result, labels=labels, annotations=annotations)

        # setup status signals
        status.connect_signals()

        # setup expected API call resulting from status update
        expected_call = {
            'apiVersion': 'fiaas.schibsted.io/v1',
            'kind': 'ApplicationStatus',
            'result': test_data.result,
            'logs': expected_logs,
            'metadata': {
                'labels': {
                    'app': app_spec.name,
                    'fiaas/deployment_id': app_spec.deployment_id,
                    'status/label': 'true'
                },
                'annotations': {
                    'fiaas/last_updated': LAST_UPDATE,
                    'status/annotations': 'true'
                },
                'namespace': 'default',
                'name': app_name,
                'ownerReferences': [],
                'finalizers': [],
            }
        }
        called_mock = request.getfixturevalue(test_data.called_mock)
        mock_response = mock.create_autospec(Response)
        mock_response.json.return_value = expected_call
        called_mock.return_value = mock_response
        lifecycle_subject = _subject_from_app_spec(app_spec)

        # this triggers the status update
        with mock.patch("fiaas_deploy_daemon.crd.status.now") as mnow:
            mnow.return_value = LAST_UPDATE
            signal(test_data.signal_name).send(status=test_data.status, subject=lifecycle_subject)

        # assert that the api function expected to be called was called, and that the ignored api function was not
        if test_data.action == "create":
            url = '/apis/fiaas.schibsted.io/v1/namespaces/default/application-statuses/'
        else:
            url = '/apis/fiaas.schibsted.io/v1/namespaces/default/application-statuses/{}'.format(app_name)

        called_mock.assert_called_once_with(url, expected_call)
        ignored_mock = request.getfixturevalue(test_data.ignored_mock)
        ignored_mock.assert_not_called()

    @pytest.mark.parametrize("deployment_id", (
            u"fiaas/fiaas-deploy-daemon:latest",
            u"1234123",
            u"The Ultimate Deployment ID",
            u"@${[]}!#%&/()=?"
    ))
    def test_create_name(self, deployment_id):
        final_name = status.create_name(NAME, deployment_id)
        assert VALID_NAME.match(final_name), "Name is not valid"

    def test_clean_up(self, app_spec, find, delete):
        returned_statuses = [_create_status(i) for i in range(20)]
        returned_statuses.append(_create_status(100, False))
        random.shuffle(returned_statuses)
        find.return_value = returned_statuses
        _cleanup(app_spec.name, app_spec.namespace)
        expected_calls = [mock.call("name-{}".format(i), "test") for i in range(20 - OLD_STATUSES_TO_KEEP)]
        expected_calls.insert(0, mock.call("name-100", "test"))
        assert delete.call_args_list == expected_calls

    def test_ignore_notfound_on_cleanup(self, find, delete, app_spec):
        delete.side_effect = NotFound()
        find.return_value = [_create_status(i) for i in range(OLD_STATUSES_TO_KEEP + 1)]

        try:
            _cleanup(app_spec.name, app_spec.namespace)
        except NotFound:
            pytest.fail("delete raised NotFound on signal")

    @pytest.mark.parametrize("result,fail_times", (
            ((result, fail_times)
             for result in (STATUS_INITIATED, STATUS_STARTED, STATUS_STARTED, STATUS_FAILED)
             for fail_times in range(5))
    ))
    @pytest.mark.usefixtures("post", "put", "find", "logs")
    def test_retry_on_conflict(self, get_or_create, save, app_spec, signal, result, fail_times):

        def _fail():
            response = mock.MagicMock(spec=Response)
            response.status_code = 409  # Conflict
            raise ClientError("Conflict", response=response)

        configure_mock_fail_then_success(save, fail=_fail, fail_times=fail_times)
        application_status = FiaasApplicationStatus(metadata=ObjectMeta(name=app_spec.name, namespace="default"))
        get_or_create.return_value = application_status

        status.connect_signals()
        lifecycle_subject = _subject_from_app_spec(app_spec)

        try:
            signal(DEPLOY_STATUS_CHANGED).send(status=result, subject=lifecycle_subject)
        except UpsertConflict as e:
            if fail_times < CONFLICT_MAX_RETRIES:
                pytest.fail('Exception {} was raised when signaling {}'.format(e, result))

        save_calls = min(fail_times + 1, CONFLICT_MAX_RETRIES)
        assert save.call_args_list == [mock.call()] * save_calls

    @pytest.mark.parametrize("result", (
            STATUS_INITIATED,
            STATUS_STARTED,
            STATUS_SUCCESS,
            STATUS_FAILED
    ))
    @pytest.mark.usefixtures("post", "put", "find", "logs")
    def test_fail_on_error(self, get_or_create, save, app_spec, signal, result):
        response = mock.MagicMock(spec=Response)
        response.status_code = 403

        save.side_effect = ClientError("No", response=response)

        application_status = FiaasApplicationStatus(metadata=ObjectMeta(name=app_spec.name, namespace="default"))
        get_or_create.return_value = application_status

        status.connect_signals()
        lifecycle_subject = _subject_from_app_spec(app_spec)

        with pytest.raises(ClientError):
            signal(DEPLOY_STATUS_CHANGED).send(status=result, subject=lifecycle_subject)


def _subject_from_app_spec(app_spec):
    return Subject(app_spec.name,
                   app_spec.namespace,
                   app_spec.deployment_id,
                   None,
                   app_spec.labels.status,
                   app_spec.annotations.status)


def _create_status(i, annotate=True):
    annotations = {LAST_UPDATED_KEY: "2020-12-12T23.59.{:02}".format(i)} if annotate else None
    metadata = ObjectMeta(name="name-{}".format(i), namespace="test", annotations=annotations)
    return FiaasApplicationStatus(new=False, metadata=metadata, result=u"SUCCESS")
