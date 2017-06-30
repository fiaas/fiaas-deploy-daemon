from collections import namedtuple

import mock
import pytest
import re
from blinker import signal

from fiaas_deploy_daemon.tpr import status
from fiaas_deploy_daemon.tpr.types import PaasbetaStatus
from k8s.models.common import ObjectMeta

DEPLOYMENT_ID = u"deployment_id"
NAME = u"name"
VALID_NAME = re.compile(r"^[a-z0-9.-]+$")


class TestStatusReport(object):
    @pytest.fixture
    def get_or_create(self):
        with mock.patch("fiaas_deploy_daemon.tpr.status.PaasbetaStatus.get_or_create", spec_set=True) as m:
            yield m

    # create vs update => new_status, url, post/put
    def pytest_generate_tests(self, metafunc):
        if metafunc.cls == self.__class__ and "test_data" in metafunc.fixturenames:
            TestData = namedtuple("TestData", ("signal_name", "action", "result", "new", "called_mock", "ignored_mock"))
            name2result = {
                "deploy_started": u"RUNNING",
                "deploy_failed": u"FAILED",
                "deploy_success": u"SUCCESS"
            }
            action2data = {
                "create": (True, "post", "put"),
                "update": (False, "put", "post")
            }
            for signal_name in ("deploy_started", "deploy_failed", "deploy_success"):
                for action in ("create", "update"):
                    test_data = TestData(signal_name, action, name2result[signal_name], *action2data[action])
                    test_id = "{} status on {}".format(action, signal_name)
                    metafunc.addcall({"test_data": test_data}, test_id)

    def test_action_on_signal(self, request, get_or_create, app_spec, test_data):
        app_name = '{}-isb5oqum36ylo'.format(test_data.signal_name)
        app_spec = app_spec._replace(name=test_data.signal_name)
        metadata = ObjectMeta(name=app_name, namespace="default", labels={
            "app": test_data.signal_name,
            "fiaas/deployment_id": app_spec.deployment_id
        })
        get_or_create.return_value = PaasbetaStatus(new=test_data.new, metadata=metadata, result=test_data.result)
        status.connect_signals()

        signal(test_data.signal_name).send(app_spec=app_spec)

        get_or_create.assert_called_once_with(metadata=metadata, result=test_data.result)
        if test_data.action == "create":
            url = '/apis/schibsted.io/v1beta/namespaces/default/paasbetastatuses/'
        else:
            url = '/apis/schibsted.io/v1beta/namespaces/default/paasbetastatuses/{}'.format(app_name)
        called_mock = request.getfixturevalue(test_data.called_mock)
        ignored_mock = request.getfixturevalue(test_data.ignored_mock)
        called_mock.assert_called_once_with(url, {
            'apiVersion': 'schibsted.io/v1beta',
            'kind': 'PaasbetaStatus',
            'result': test_data.result,
            'metadata': {
                'labels': {
                    'app': test_data.signal_name,
                    'fiaas/deployment_id': app_spec.deployment_id
                },
                'namespace': 'default',
                'name': app_name}})
        ignored_mock.assert_not_called()

    @pytest.mark.parametrize("deployment_id", (
            u"containers.schibsted.io/finntech/fiaas-deploy-daemon:lastest",
            u"1234123",
            u"The Ultimate Deployment ID",
            u"@${[]}!#%&/()=?"
    ))
    def test_create_name(self, deployment_id):
        final_name = status.create_name(NAME, deployment_id)
        assert VALID_NAME.match(final_name), "Name is not valid"
