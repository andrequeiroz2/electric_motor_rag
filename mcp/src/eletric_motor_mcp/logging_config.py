"""Structured stderr logging for the MCP server."""

import json
import logging
import sys
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname.lower(),
            "event": getattr(record, "event", "mcp.log"),
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("tool", "latency_ms", "formula_set_version"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level_name: str) -> None:
    level = logging.getLevelNamesMapping().get(level_name.upper(), logging.INFO)
    root = logging.getLogger("eletric_motor_mcp")
    root.setLevel(level)
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)
    root.propagate = False


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"eletric_motor_mcp.{name}")
