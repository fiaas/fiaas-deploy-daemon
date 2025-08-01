import logging

from fiaas_deploy_daemon.log_metrics import MetricsHandler, fiaas_log_records


def test_metrics_handler():
    log = logging.getLogger("test_metrics_handler")
    log.addHandler(MetricsHandler())
    log.setLevel(logging.DEBUG)

    log.debug("debug")
    log.info("info")
    log.warning("warning")
    log.error("error")
    try:
        raise RuntimeError("exception")
    except RuntimeError:
        log.exception("exception")

    expected = {
        "DEBUG": 1.0,
        "INFO": 1.0,
        "WARNING": 1.0,
        "ERROR": 2.0,
    }

    [metric] = fiaas_log_records.collect()
    for level, value in expected.items():
        assert any(
            sample.name == "fiaas_log_records_total" and sample.labels == {"level": level} and sample.value == value
            for sample in metric.samples
        ), f"fiaas_log_records_total with labels level={level} and value={value} was not in the collected samples"
