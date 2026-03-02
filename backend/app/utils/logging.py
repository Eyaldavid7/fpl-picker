"""Structured JSON logging configuration.

Configures Python's built-in logging module to emit structured JSON log
records that include timestamp, module, level, and message.  The log
level defaults to DEBUG when the application is in debug mode, and INFO
otherwise.

Usage::

    from app.utils.logging import setup_logging

    setup_logging(debug=True)
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """Logging formatter that outputs each record as a single JSON object.

    Each log line contains the following fields:
    - timestamp: ISO-8601 UTC timestamp
    - level: log level name (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - module: the Python module that emitted the log
    - message: the formatted log message
    - logger: the logger name
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a JSON string.

        Args:
            record: The log record to format.

        Returns:
            A single-line JSON string representing the log entry.
        """
        log_entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info and record.exc_info[1] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def setup_logging(debug: bool = False) -> None:
    """Configure the root logger with structured JSON output.

    Args:
        debug: When True, sets the log level to DEBUG. Otherwise uses INFO.
    """
    level = logging.DEBUG if debug else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root_logger = logging.getLogger()
    # Remove any existing handlers to avoid duplicate output
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    # Quieten noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
