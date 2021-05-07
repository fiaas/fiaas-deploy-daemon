
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

from __future__ import absolute_import

import logging
from datetime import datetime

import pytz
from blinker import signal
from k8s.client import NotFound
from k8s.models.common import ObjectMeta, OwnerReference

from .types import FiaasApplicationStatus
from ..lifecycle import DEPLOY_STATUS_CHANGED, STATUS_STARTED
from ..log_extras import get_final_logs, get_running_logs
from ..retry import retry_on_upsert_conflict
from ..tools import merge_dicts

LAST_UPDATED_KEY = "fiaas/last_updated"
OLD_STATUSES_TO_KEEP = 10
LOG = logging.getLogger(__name__)


def connect_signals():
    signal(DEPLOY_STATUS_CHANGED).connect(_handle_signal)


def now():
    now = datetime.utcnow()
    now = pytz.utc.localize(now)
    return now.isoformat()


def find_status(namespace, app_name, deployment_id):
    selector = {
        "app": app_name,
        "fiaas/deployment_id": deployment_id,
    }
    statuses = FiaasApplicationStatus.find(namespace=namespace, labels=selector)
    # sort by creationTimestamp in case of more than one result (could happen in transition from py2 to py3)
    statuses.sort(key=lambda status: status.metadata.creationTimestamp, reverse=True)
    if len(statuses) > 1:
        LOG.warn("Found %d ApplicationStatuses for %s/%s deployment_id=%s", len(statuses), namespace, app_name, deployment_id)
    if statuses:
        return statuses[0]
    else:
        return None


def _handle_signal(sender, status, subject):
    if status == STATUS_STARTED:
        status = "RUNNING"
    else:
        status = status.upper()

    _save_status(status, subject)
    _cleanup(subject.app_name, subject.namespace)


@retry_on_upsert_conflict
def _save_status(result, subject):
    (uid, app_name, namespace, deployment_id, repository, labels, annotations) = subject
    LOG.info("Saving result %s for %s/%s deployment_id=%s", result, namespace, app_name, deployment_id)
    labels = labels or {}
    annotations = annotations or {}
    labels = merge_dicts(labels, {"app": app_name, "fiaas/deployment_id": deployment_id})
    annotations = merge_dicts(annotations, {LAST_UPDATED_KEY: now()})
    logs = _get_logs(app_name, namespace, deployment_id, result)

    status = find_status(namespace, app_name, deployment_id)
    if status is not None:
        status.metadata.labels = merge_dicts(status.metadata.labels, labels)
        status.metadata.annotations = merge_dicts(status.metadata.annotations, annotations)
        status.logs = logs
        status.result = result
    else:
        metadata = ObjectMeta(generateName="{}-".format(app_name), namespace=namespace, labels=labels, annotations=annotations)
        status = FiaasApplicationStatus(metadata=metadata, result=result, logs=logs)
    resource_version = status.metadata.resourceVersion

    LOG.debug("save()-ing %s for %s/%s deployment_id=%s resourceVersion=%s", result, namespace, app_name,
              deployment_id, resource_version)
    _apply_owner_reference(status, subject)
    status.save()


def _get_logs(app_name, namespace, deployment_id, result):
    return get_running_logs(app_name, namespace, deployment_id) if result in [u"RUNNING", u"INITIATED"] else \
           get_final_logs(app_name, namespace, deployment_id)


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


def _apply_owner_reference(status, subject):
    if subject.uid:
        owner_reference = OwnerReference(apiVersion="fiaas.schibsted.io/v1",
                                         blockOwnerDeletion=True,
                                         controller=True,
                                         kind="Application",
                                         name=subject.app_name,
                                         uid=subject.uid)

        status.metadata.ownerReferences = [owner_reference]
