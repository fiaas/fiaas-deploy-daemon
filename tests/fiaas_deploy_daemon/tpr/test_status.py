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

    @pytest.mark.parametrize("signal_name,result", (
            ("deploy_started", u"RUNNING"),
            ("deploy_failed", u"FAILED"),
            ("deploy_success", u"SUCCESS")
    ))
    def test_create_status_on_signal(self, signal_name, result, get_or_create, post, put):
        app_name = '{}-7ka6gav5mq2hc'.format(signal_name)
        metadata = ObjectMeta(name=app_name, namespace="default", labels={
            "app": signal_name
        }, annotations={
            "fiaas/deployment_id": DEPLOYMENT_ID
        })
        get_or_create.return_value = PaasbetaStatus(new=True, metadata=metadata, result=result)
        status.connect_signals()

        signal(signal_name).send(deployment_id=DEPLOYMENT_ID, name=signal_name)

        get_or_create.assert_called_once_with(metadata=metadata, result=result)
        post.assert_called_once_with('/apis/schibsted.io/v1beta/namespaces/default/paasbetastatuses/', {
            'apiVersion': 'schibsted.io/v1beta',
            'kind': 'PaasbetaStatus',
            'result': result,
            'metadata': {
                'labels': {
                    'app': signal_name
                },
                'annotations': {
                    'fiaas/deployment_id': DEPLOYMENT_ID
                },
                'namespace': 'default',
                'name': app_name}})
        put.assert_not_called()

    @pytest.mark.parametrize("signal_name,result", (
            ("deploy_started", u"RUNNING"),
            ("deploy_failed", u"FAILED"),
            ("deploy_success", u"SUCCESS")
    ))
    def test_update_status_on_signal(self, signal_name, result, get_or_create, post, put):
        app_name = '{}-7ka6gav5mq2hc'.format(signal_name)
        metadata = ObjectMeta(name=app_name, namespace="default", labels={
            "app": signal_name
        }, annotations={
            "fiaas/deployment_id": DEPLOYMENT_ID
        })
        get_or_create.return_value = PaasbetaStatus(new=False, metadata=metadata, result=result)
        status.connect_signals()

        signal(signal_name).send(deployment_id=DEPLOYMENT_ID, name=signal_name)

        get_or_create.assert_called_once_with(metadata=metadata, result=result)
        post.assert_not_called()
        put.assert_called_once_with(
            '/apis/schibsted.io/v1beta/namespaces/default/paasbetastatuses/{}'.format(app_name), {
                'apiVersion': 'schibsted.io/v1beta',
                'kind': 'PaasbetaStatus',
                'result': result,
                'metadata': {
                    'labels': {
                        'app': signal_name
                    },
                    'annotations': {
                        'fiaas/deployment_id': DEPLOYMENT_ID
                    },
                    'namespace': 'default',
                    'name': app_name}})

    @pytest.mark.parametrize("deployment_id", (
            u"containers.schibsted.io/finntech/fiaas-deploy-daemon:lastest",
            u"1234123",
            u"The Ultimate Deployment ID",
            u"@${[]}!#%&/()=?"
    ))
    def test_create_name(self, deployment_id):
        final_name = status.create_name(NAME, deployment_id)
        assert VALID_NAME.match(final_name), "Name is not valid"
