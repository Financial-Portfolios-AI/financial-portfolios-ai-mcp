"""Logs are one JSON object per line, so a record arrives as one queryable entry."""

import json
import logging

from financial_portfolios_ai_mcp.logging_setup import JsonFormatter, configure_logging


def _format(record: logging.LogRecord) -> dict:
    return json.loads(JsonFormatter().format(record))


def _record(message="hello", level=logging.INFO, **extra) -> logging.LogRecord:
    record = logging.LogRecord("test.logger", level, __file__, 10, message, None, None)
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_record_is_one_line_of_json_with_cloud_logging_severity():
    text = JsonFormatter().format(_record("portal_retry"))
    assert "\n" not in text
    payload = json.loads(text)
    assert payload["severity"] == "INFO"
    assert payload["message"] == "portal_retry"
    assert payload["logger"] == "test.logger"


def test_structured_fields_are_kept_as_fields():
    """The capability report and retry warnings carry fields, not prose - that is what
    makes them filterable. Before this, a long record was wrapped across entries."""
    payload = _format(_record("explorer_host_report", host={"name": "ClaudeAndroid"}, style_variables=76))
    assert payload["host"] == {"name": "ClaudeAndroid"}
    assert payload["style_variables"] == 76


def test_unserialisable_fields_do_not_break_a_log_line():
    payload = _format(_record("odd", thing=object()))
    assert isinstance(payload["thing"], str)


def test_exceptions_are_included():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = _record("failed", level=logging.ERROR)
        record.exc_info = sys.exc_info()
    payload = _format(record)
    assert payload["severity"] == "ERROR"
    assert "ValueError: boom" in payload["exception"]


def test_configure_logging_is_idempotent_and_quiets_httpx():
    original_handlers = logging.getLogger().handlers[:]
    original_level = logging.getLogger().level
    try:
        configure_logging("DEBUG", force=True)
        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, JsonFormatter)
        assert root.level == logging.DEBUG
        # Uvicorn's loggers share the handler instead of printing their own format.
        assert logging.getLogger("uvicorn.access").handlers == root.handlers
        # httpx logs every portal request at INFO; that is noise.
        assert logging.getLogger("httpx").level >= logging.WARNING

        configure_logging("ERROR")  # no force: must not reconfigure
        assert logging.getLogger().level == logging.DEBUG
    finally:
        logging.getLogger().handlers = original_handlers
        logging.getLogger().setLevel(original_level)
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "mcp"):
            logging.getLogger(name).handlers = []
            logging.getLogger(name).propagate = True
