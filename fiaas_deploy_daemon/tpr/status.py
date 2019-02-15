from __future__ import absolute_import

import logging
import struct
from base64 import b32encode
from datetime import datetime
from functools import partial

import pytz
from blinker import signal
from k8s.models.common import ObjectMeta

from .types import PaasbetaStatus
from ..retry import retry_on_upsert_conflict
from ..lifecycle import DEPLOY_FAILED, DEPLOY_STARTED, DEPLOY_SUCCESS, DEPLOY_INITIATED
from ..log_extras import get_final_logs, get_running_logs

LAST_UPDATED_KEY = "fiaas/last_updated"
OLD_STATUSES_TO_KEEP = 10
LOG = logging.getLogger(__name__)


def connect_signals():
    signal(DEPLOY_STARTED).connect(_handle_started)
    signal(DEPLOY_FAILED).connect(_handle_failed)
    signal(DEPLOY_SUCCESS).connect(_handle_success)
    signal(DEPLOY_INITIATED).connect(_handle_initiated)


def now():
    now = datetime.utcnow()
    now = pytz.utc.localize(now)
    return now.isoformat()


def _handle_signal(result, sender, app_name, namespace, deployment_id, repository):
    _save_status(app_name, namespace, deployment_id, result)
    _cleanup(app_name, namespace)


@retry_on_upsert_conflict
def _save_status(app_name, namespace, deployment_id, result):
    LOG.info("Saving result %s for %s/%s", result, namespace, app_name)
    name = create_name(app_name, deployment_id)
    labels = {"app": app_name, "fiaas/deployment_id": deployment_id}
    annotations = {LAST_UPDATED_KEY: now()}
    metadata = ObjectMeta(name=name, namespace=namespace, labels=labels, annotations=annotations)
    logs = _get_logs(app_name, namespace, deployment_id, result)
    status = PaasbetaStatus.get_or_create(metadata=metadata, result=result, logs=logs)
    resource_version = status.metadata.resourceVersion
    LOG.debug("save()-ing %s for %s/%s deployment_id=%s resourceVersion=%s", result, namespace, app_name,
              deployment_id, resource_version)
    status.save()


def _get_logs(app_name, namespace, deployment_id, result):
    return get_running_logs(app_name, namespace, deployment_id) if result in [u"RUNNING", u"INITIATED"] else \
           get_final_logs(app_name, namespace, deployment_id)


def _cleanup(app_name, namespace):
    statuses = PaasbetaStatus.find(app_name, namespace)

    def _last_updated(s):
        annotations = s.metadata.annotations
        return annotations.get(LAST_UPDATED_KEY, "") if annotations else ""

    statuses.sort(key=_last_updated)
    for old_status in statuses[:-OLD_STATUSES_TO_KEEP]:
        PaasbetaStatus.delete(old_status.metadata.name, old_status.metadata.namespace)


_handle_started = partial(_handle_signal, u"RUNNING")
_handle_failed = partial(_handle_signal, u"FAILED")
_handle_success = partial(_handle_signal, u"SUCCESS")
_handle_initiated = partial(_handle_signal, u"INITIATED")


def create_name(name, deployment_id):
    """Create a name for the status object

    By convention, the names of Kubernetes resources should be up to maximum length of 253
    characters and consist of lower case alphanumeric characters, '-', and '.'.
    """
    suffix = b32encode(struct.pack('q', hash(deployment_id))).lower().strip("=")
    return "{}-{}".format(name, suffix)
