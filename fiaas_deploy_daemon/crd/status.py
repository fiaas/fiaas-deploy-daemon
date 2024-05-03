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


import logging
import struct
from base64 import b32encode
from datetime import datetime, timezone

from blinker import signal
from py27hash.hash import hash27
from k8s.client import NotFound
from k8s.models.common import ObjectMeta, OwnerReference

from .types import FiaasApplication, FiaasApplicationStatus, FiaasApplicationStatusResult
from ..lifecycle import DEPLOY_STATUS_CHANGED, STATUS_STARTED
from ..log_extras import get_final_error_logs, get_final_logs, get_running_error_logs, get_running_logs
from ..retry import retry_on_upsert_conflict
from ..tools import merge_dicts

LAST_UPDATED_KEY = "fiaas/last_updated"
OLD_STATUSES_TO_KEEP = 10
LOG = logging.getLogger(__name__)


def connect_signals(include_status_in_app):
    if include_status_in_app:
        signal(DEPLOY_STATUS_CHANGED).connect(_handle_signal_with_status)
    else:
        signal(DEPLOY_STATUS_CHANGED).connect(_handle_signal_without_status)


def now():
    return datetime.now(timezone.utc).isoformat()


def _handle_signal_without_status(sender, status, subject):
    if status == STATUS_STARTED:
        status = "RUNNING"
    else:
        status = status.upper()

    _save_status(status, subject)
    _cleanup(subject.app_name, subject.namespace)


def _handle_signal_with_status(sender, status, subject):
    if status == STATUS_STARTED:
        status = "RUNNING"
    else:
        status = status.upper()

    _save_status_inline(status, subject)
    _save_status(status, subject)
    _cleanup(subject.app_name, subject.namespace)


@retry_on_upsert_conflict
def _save_status_inline(result, subject):
    (uid, app_name, namespace, deployment_id, repository, labels, annotations) = subject

    app = FiaasApplication.get(app_name, namespace)
    generation = int(app.metadata.generation)
    try:
        application_deployment_id = app.metadata.labels["fiaas/deployment_id"]
    except (AttributeError, KeyError, TypeError):
        raise ValueError("The Application {} is missing the 'fiaas/deployment_id' label".format(app_name))
    # We only want to get error logs here.
    if deployment_id == application_deployment_id:
        logs = _get_error_logs(app_name, namespace, deployment_id, result)

        LOG.info("Saving inline result %s for %s/%s deployment_id=%s generation %s", result, namespace, app_name, deployment_id, generation)
        app.status = FiaasApplicationStatusResult(observedGeneration=generation, result=result, logs=logs,
                                                  deployment_id=deployment_id)
        app.save_status()
    else:
        LOG.debug("Skipping saving status for application %s with different deployment_id", app_name)


@retry_on_upsert_conflict
def _save_status(result, subject):
    (uid, app_name, namespace, deployment_id, repository, labels, annotations) = subject
    LOG.info("Saving result %s for %s/%s deployment_id=%s", result, namespace, app_name, deployment_id)
    name = create_name(app_name, deployment_id)
    labels = labels or {}
    annotations = annotations or {}
    labels = merge_dicts(labels, {"app": app_name, "fiaas/deployment_id": deployment_id})
    annotations = merge_dicts(annotations, {LAST_UPDATED_KEY: now()})
    logs = _get_logs(app_name, namespace, deployment_id, result)

    try:
        status = FiaasApplicationStatus.get(name, namespace)
        status.metadata.labels = merge_dicts(status.metadata.labels, labels)
        status.metadata.annotations = merge_dicts(status.metadata.annotations, annotations)
        status.logs = logs
        status.result = result
    except NotFound:
        metadata = ObjectMeta(name=name, namespace=namespace, labels=labels, annotations=annotations)
        status = FiaasApplicationStatus.get_or_create(metadata=metadata, result=result, logs=logs)
    resource_version = status.metadata.resourceVersion

    LOG.debug(
        "save()-ing %s for %s/%s deployment_id=%s resourceVersion=%s",
        result,
        namespace,
        app_name,
        deployment_id,
        resource_version,
    )
    _apply_owner_reference(status, subject)
    status.save()


def _get_logs(app_name, namespace, deployment_id, result):
    return (
        get_running_logs(app_name, namespace, deployment_id)
        if result in ["RUNNING", "INITIATED"]
        else get_final_logs(app_name, namespace, deployment_id)
    )


def _get_error_logs(app_name, namespace, deployment_id, result):
    return get_running_error_logs(app_name, namespace, deployment_id) if result in [u"RUNNING", u"INITIATED"] else \
       get_final_error_logs(app_name, namespace, deployment_id)


def _cleanup(app_name=None, namespace=None):
    statuses = FiaasApplicationStatus.find(app_name, namespace)

    def _last_updated(s):
        annotations = s.metadata.annotations
        return annotations.get(LAST_UPDATED_KEY, "") if annotations else ""

    statuses.sort(key=_last_updated)
    for old_status in statuses[:-OLD_STATUSES_TO_KEEP]:
        try:
            FiaasApplicationStatus.delete(old_status.metadata.name, old_status.metadata.namespace)
        except NotFound:
            pass  # already deleted


def create_name(name, deployment_id):
    """Create a name for the status object

    By convention, the names of Kubernetes resources should be up to maximum length of 253
    characters and consist of lower case alphanumeric characters, '-', and '.'.
    """
    suffix = b32encode(struct.pack("q", hash27(deployment_id))).decode("utf-8").lower().strip("=")
    return "{}-{}".format(name, suffix)


def _apply_owner_reference(status, subject):
    if subject.uid:
        owner_reference = OwnerReference(
            apiVersion="fiaas.schibsted.io/v1",
            blockOwnerDeletion=True,
            controller=True,
            kind="Application",
            name=subject.app_name,
            uid=subject.uid,
        )

        status.metadata.ownerReferences = [owner_reference]
