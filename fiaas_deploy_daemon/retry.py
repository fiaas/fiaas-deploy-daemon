
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

import functools
import inspect
import sys

import backoff
from prometheus_client import Counter
from k8s.client import ClientError


CONFLICT_MAX_RETRIES = 2
CONFLICT_MAX_VALUE = 3

fiaas_upsert_conflict_retry_counter = Counter(
    "fiaas_upsert_conflict_retry",
    "Number of retries made due to 409 Conflict when upserting a Kubernetes resource",
    ["target"]
)
fiaas_upsert_conflict_failure_counter = Counter(
    "fiaas_upsert_conflict_failure",
    "Number of times max retries were exceeded due to 409 Conflict when upserting a Kubernetes resource",
    ["target"]
)


class UpsertConflict(Exception):
    def __init__(self, cause, response):
        self.traceback = sys.exc_info()
        super(self.__class__, self).__init__(cause.message)
        self.response = response

    def __str__(self):
        status_json = self.response.json()
        # `reason=Conflict` means resourceVersion we tried to PUT was lower than the resourceVersion of the resource
        # on the server.
        # `reason=AlreadyExists` means we tried to POST to the url of a resource that already exists on the server,
        # and we should try again with a PUT.
        reason = status_json["reason"]
        message = status_json["message"]
        return "{status_code} Conflict for {method} {url}. reason={reason}, message={message}".format(
            status_code=self.response.status_code,
            method=self.response.request.method,
            url=self.response.request.url,
            message=message,
            reason=reason
        )


def _count_retry(target, *args, **kwargs):
    return fiaas_upsert_conflict_retry_counter.labels(target=target).inc()


def _count_failure(target, *args, **kwargs):
    return fiaas_upsert_conflict_failure_counter.labels(target=target).inc()


def canonical_name(func):
    if inspect.ismethod(func):
        # method's class is im_class, classmethod's class is im_self
        method_cls = func.im_class if func.im_self is None else func.im_self
        for cls in inspect.getmro(method_cls):
            if func.__name__ in cls.__dict__:
                return "{}.{}.{}".format(cls.__module__, cls.__name__, func.__name__)
    return "{}.{}".format(func.__module__, func.__name__)


def retry_on_upsert_conflict(_func=None, max_value_seconds=CONFLICT_MAX_VALUE, max_tries=CONFLICT_MAX_RETRIES):
    def _retry_decorator(func):
        target = canonical_name(func)

        @backoff.on_exception(backoff.expo, UpsertConflict,
                              max_value=max_value_seconds,
                              max_tries=max_tries,
                              on_backoff=functools.partial(_count_retry, target),
                              on_giveup=functools.partial(_count_failure, target))
        @functools.wraps(func)
        def _wrap(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ClientError as e:
                if e.response.status_code == 409:  # Conflict
                    raise UpsertConflict(e, e.response)
                else:
                    raise
        return _wrap

    if _func is None:
        return _retry_decorator
    else:
        return _retry_decorator(_func)
