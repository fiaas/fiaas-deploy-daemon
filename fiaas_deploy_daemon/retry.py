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
    def __init__(self, cause):
        self.traceback = sys.exc_info()
        super(self.__class__, self).__init__(cause.message)


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


def retry_on_upsert_conflict(_func=None, max_value=CONFLICT_MAX_VALUE, max_tries=CONFLICT_MAX_RETRIES):
    def _retry_decorator(func):
        target = canonical_name(func)

        @backoff.on_exception(backoff.expo, UpsertConflict,
                              max_value=max_value,
                              max_tries=max_tries,
                              on_backoff=functools.partial(_count_retry, target),
                              on_giveup=functools.partial(_count_failure, target))
        @functools.wraps(func)
        def _wrap(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ClientError as e:
                if e.response.status_code == 409:  # Conflict
                    raise UpsertConflict(e)
                else:
                    raise
        return _wrap

    if _func is None:
        return _retry_decorator
    else:
        return _retry_decorator(_func)
