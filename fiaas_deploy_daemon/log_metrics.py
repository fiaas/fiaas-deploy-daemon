import logging

from prometheus_client import Counter

fiaas_log_records = Counter(
    "fiaas_log_records",
    "Number of records logged by the application, by level",
    ["level"],
)


class MetricsHandler(logging.Handler):
    def __init__(self):
        super().__init__()

    def emit(self, record: logging.LogRecord):
        fiaas_log_records.labels(level=record.levelname).inc()
