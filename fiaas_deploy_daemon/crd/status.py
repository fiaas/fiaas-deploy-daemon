from __future__ import absolute_import

from functools import partial
from base64 import b32encode
import struct

from blinker import signal

from k8s.models.common import ObjectMeta
from .types import FiaasStatus
from ..deployer.bookkeeper import DEPLOY_FAILED, DEPLOY_STARTED, DEPLOY_SUCCESS


def connect_signals():
    signal(DEPLOY_STARTED).connect(_handle_started)
    signal(DEPLOY_FAILED).connect(_handle_failed)
    signal(DEPLOY_SUCCESS).connect(_handle_success)


def _handle_signal(result, sender, app_spec):
    name = create_name(app_spec.name, app_spec.deployment_id)
    metadata = ObjectMeta(name=name, namespace=app_spec.namespace, labels={
        "app": app_spec.name,
        "fiaas/deployment_id": app_spec.deployment_id
    })
    status = FiaasStatus.get_or_create(metadata=metadata, result=result)
    status.save()


_handle_started = partial(_handle_signal, u"RUNNING")
_handle_failed = partial(_handle_signal, u"FAILED")
_handle_success = partial(_handle_signal, u"SUCCESS")


def create_name(name, deployment_id):
    """Create a name for the status object

    By convention, the names of Kubernetes resources should be up to maximum length of 253
    characters and consist of lower case alphanumeric characters, '-', and '.'.
    """
    suffix = b32encode(struct.pack('q', hash(deployment_id))).lower().strip("=")
    return "{}-{}".format(name, suffix)
