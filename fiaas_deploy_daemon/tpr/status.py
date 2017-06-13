from __future__ import absolute_import

from functools import partial
from base64 import b32encode
import struct

from blinker import signal

from k8s.models.common import ObjectMeta
from .types import PaasbetaStatus


def connect_signals():
    signal("deploy_started").connect(_handle_started)
    signal("deploy_failed").connect(_handle_failed)
    signal("deploy_success").connect(_handle_success)


def _handle_signal(result, sender, deployment_id, name):
    # TODO: Select a namespace
    metadata = ObjectMeta(name=create_name(name, deployment_id), labels={
        "app": name
    }, annotations={
        "fiaas/deployment_id": deployment_id
    })
    status = PaasbetaStatus.get_or_create(metadata=metadata, result=result)
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
