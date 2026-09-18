"""Logging for the served app.

`setup_logging` in the CLI only runs for `stdio`/`serve` invocations. The container runs
`uvicorn financial_portfolios_ai_mcp.app:app` directly, so nothing configured the root
logger and records reached Cloud Logging through the MCP SDK's console formatter, wrapped
at the console's default width: a single JSON log line arrived split across a dozen
entries, unqueryable.

One JSON object per line instead, with the `severity` field Cloud Logging reads, so a log
entry is one entry and can be filtered on `jsonPayload`.
"""

import json
import logging
import os
import sys

_CONFIGURED = "_fpai_logging_configured"

# Attributes of a LogRecord that are not extras; anything else a caller attaches is kept.
_RESERVED = frozenset(
    ["args", "asctime", "created", "exc_info", "exc_text", "filename", "funcName", "levelname", "levelno", "lineno", "module", "msecs", "message", "msg", "name", "pathname", "process", "processName", "relativeCreated", "stack_info", "stacklevel", "thread", "threadName", "taskName"]
)


class JsonFormatter(logging.Formatter):
    """Render a record as one line of JSON, Cloud Logging's field names where they exist."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                try:
                    json.dumps(value)
                except TypeError:
                    value = repr(value)
                payload[key] = value
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO", *, force: bool = False) -> None:
    """Send this process's logs to stdout as JSON lines. Idempotent.

    Uvicorn's own loggers are re-pointed at the same handler so access logs and ours
    share a format. Called from `create_app()`, so it applies however the app is served.
    """
    root = logging.getLogger()
    if getattr(root, _CONFIGURED, False) and not force:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    resolved = getattr(logging, str(level).upper(), logging.INFO)
    root.handlers = [handler]
    root.setLevel(resolved)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "mcp"):
        logger = logging.getLogger(name)
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(resolved)

    # httpx logs every portal request at INFO; that is noise at our default level.
    logging.getLogger("httpx").setLevel(max(resolved, logging.WARNING))

    setattr(root, _CONFIGURED, True)


def log_level_from_env(default: str = "INFO") -> str:
    return os.environ.get("MCP_LOG_LEVEL", default)
