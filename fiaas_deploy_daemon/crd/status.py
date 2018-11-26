from __future__ import absolute_import

import logging
import struct
from base64 import b32encode
from datetime import datetime
from functools import partial

import pytz
from blinker import signal
from k8s.models.common import ObjectMeta

from .types import FiaasApplicationStatus
from ..deployer.bookkeeper import DEPLOY_FAILED, DEPLOY_STARTED, DEPLOY_SUCCESS
from ..log_extras import get_final_logs, get_running_logs

LAST_UPDATED_KEY = "fiaas/last_updated"
OLD_STATUSES_TO_KEEP = 10
LOG = logging.getLogger(__name__)


def connect_signals():
    signal(DEPLOY_STARTED).connect(_handle_started)
    signal(DEPLOY_FAILED).connect(_handle_failed)
    signal(DEPLOY_SUCCESS).connect(_handle_success)


def now():
    now = datetime.utcnow()
    now = pytz.utc.localize(now)
    return now.isoformat()


def _handle_signal(result, sender, app_spec=None, app_name=None, namespace=None, deployment_id=None):
    _save_status(app_spec, app_name, namespace, deployment_id, result)
    _cleanup(app_spec, app_name, namespace)


def _save_status(app_spec, app_name, namespace, deployment_id, result):
    if app_spec:
        namespace = app_spec.namespace
        app_name = app_spec.name
        deployment_id = app_spec.deployment_id
    LOG.info("Saving result %s for %s/%s", result, namespace, app_name)
    name = create_name(app_name, deployment_id)
    labels = {"app": app_name, "fiaas/deployment_id": deployment_id}
    annotations = {LAST_UPDATED_KEY: now()}
    metadata = ObjectMeta(name=name, namespace=namespace, labels=labels, annotations=annotations)
    logs = _get_logs(app_spec, app_name, namespace, deployment_id, result)
    status = FiaasApplicationStatus.get_or_create(metadata=metadata, result=result, logs=logs)
    status.save()


def _get_logs(app_spec, app_name, namespace, deployment_id, result):
    return get_running_logs(app_spec, app_name, namespace, deployment_id) if result == u"RUNNING" else \
           get_final_logs(app_spec, app_name, namespace, deployment_id)


def _cleanup(app_spec=None, app_name=None, namespace=None):
    if app_spec:
        namespace = app_spec.namespace
        app_name = app_spec.name
    statuses = FiaasApplicationStatus.find(app_name, namespace)

    def _last_updated(s):
        annotations = s.metadata.annotations
        return annotations.get(LAST_UPDATED_KEY, "") if annotations else ""

    statuses.sort(key=_last_updated)
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
