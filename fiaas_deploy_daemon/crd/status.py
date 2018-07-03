from __future__ import absolute_import

import struct
from base64 import b32encode
from datetime import datetime
from functools import partial

import pytz
from blinker import signal
from k8s.models.common import ObjectMeta

from .types import FiaasApplicationStatus
from ..deployer.bookkeeper import DEPLOY_FAILED, DEPLOY_STARTED, DEPLOY_SUCCESS

LAST_UPDATED_KEY = "fiaas/last_updated"
OLD_STATUSES_TO_KEEP = 10


def connect_signals():
    signal(DEPLOY_STARTED).connect(_handle_started)
    signal(DEPLOY_FAILED).connect(_handle_failed)
    signal(DEPLOY_SUCCESS).connect(_handle_success)


def now():
    now = datetime.utcnow()
    now = pytz.utc.localize(now)
    return now.isoformat()


def _handle_signal(result, sender, app_spec):
    _save_status(app_spec, result)
    _cleanup(app_spec)


def _save_status(app_spec, result):
    name = create_name(app_spec.name, app_spec.deployment_id)
    labels = {"app": app_spec.name, "fiaas/deployment_id": app_spec.deployment_id}
    annotations = {LAST_UPDATED_KEY: now()}
    metadata = ObjectMeta(name=name, namespace=app_spec.namespace, labels=labels, annotations=annotations)
    status = FiaasApplicationStatus.get_or_create(metadata=metadata, result=result)
    status.save()


def _cleanup(app_spec):
    statuses = FiaasApplicationStatus.find(app_spec.name, app_spec.namespace)
    statuses.sort(key=lambda s: s.metadata.annotations.get(LAST_UPDATED_KEY, ""))
    for old_status in statuses[:-OLD_STATUSES_TO_KEEP]:
        FiaasApplicationStatus.delete(old_status.metadata.name, old_status.metadata.namespace)


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
