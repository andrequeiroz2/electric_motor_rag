import json
import logging
import sys
import time
import traceback
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
_configured = False

LevelName = Literal["debug", "info", "warning", "error"]
_LEVELS: dict[LevelName, int] = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


class TraceContext(BaseModel, frozen=True):
    model_config = ConfigDict(extra="forbid")

    collection: str | None = None
    created: bool | None = None
    indexes_added: tuple[str, ...] | None = None
    dense_size: int | None = None
    dense_vector_name: str | None = None
    sparse_vector_name: str | None = None
    document_id: str | None = None
    pages: int | None = Field(default=None, ge=1)
    sections: int | None = Field(default=None, ge=0)
    chunks: int | None = Field(default=None, ge=0)
    points_written: int | None = Field(default=None, ge=0)
    points_existing: int | None = Field(default=None, ge=0)
    points_updated: int | None = Field(default=None, ge=0)
    span: str | None = None
    filters: dict[str, str] | None = None
    dense_hits: int | None = Field(default=None, ge=0)
    sparse_hits: int | None = Field(default=None, ge=0)
    fused_hits: int | None = Field(default=None, ge=0)
    llm_model: str | None = None
    answer_chars: int | None = Field(default=None, ge=0)
    rerank_model: str | None = None
    rerank_candidates: int | None = Field(default=None, ge=0)
    cache_scope: str | None = None
    cache_hit: bool | None = None
    mcp_tool_count: int | None = Field(default=None, ge=0)
    mcp_tool_names: tuple[str, ...] | None = None
    latency_ms: int | None = None
    error_type: str | None = None
    error_message: str | None = None
    error_file: str | None = None
    error_line: int | None = Field(default=None, ge=1)
    error_function: str | None = None


class LogEvent(TraceContext, frozen=True):
    ts: str
    level: LevelName
    event: str
    trace_id: str = Field(min_length=1)
    logger: str = Field(min_length=1)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line = getattr(record, "trace_line", None)
        if isinstance(line, str):
            return line
        payload = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname.lower(),
            "event": record.getMessage(),
            "trace_id": _trace_id.get() or "",
            "logger": record.name,
        }
        return json.dumps(payload, ensure_ascii=False)


@contextmanager
def trace_scope() -> Iterator[str]:
    trace_id = uuid.uuid4().hex
    token = _trace_id.set(trace_id)
    try:
        yield trace_id
    finally:
        _trace_id.reset(token)


def current_trace_id() -> str | None:
    return _trace_id.get()


def bind_trace() -> Token[str | None] | None:
    if _trace_id.get() is not None:
        return None
    return _trace_id.set(uuid.uuid4().hex)


def release_trace(token: Token[str | None] | None) -> None:
    if token is not None:
        _trace_id.reset(token)


def elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def error_origin(exc: BaseException) -> tuple[str, int, str] | None:
    package_root = Path(__file__).resolve().parents[1]
    chosen = None
    for frame in traceback.extract_tb(exc.__traceback__):
        path = Path(frame.filename).resolve()
        try:
            path.relative_to(package_root)
        except ValueError:
            continue
        chosen = frame
    if chosen is None:
        return None
    relative = Path(chosen.filename).resolve().relative_to(package_root.parent)
    return str(relative), chosen.lineno, chosen.name


def error_message(exc: BaseException) -> str:
    if isinstance(exc, UnexpectedResponse):
        content = exc.content.decode(errors="replace") if exc.content else ""
        return f"Qdrant recusou a requisição ({exc.status_code}): {content}"[:200]
    if isinstance(exc, ResponseHandlingException):
        return "Falha ao falar com o Qdrant"
    text = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
    return text[:200]


def log_event(
    event: str,
    *,
    level: LevelName = "info",
    logger_name: str,
    context: TraceContext | None = None,
) -> None:
    trace_id = _trace_id.get()
    if trace_id is None:
        raise RuntimeError("trace_id ausente")
    _configure()
    fields = {} if context is None else context.model_dump(exclude_none=True)
    payload = LogEvent(
        ts=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        level=level,
        event=event,
        trace_id=trace_id,
        logger=logger_name,
        **fields,
    )
    data = payload.model_dump(exclude_none=True, mode="json")
    ordered = {key: data.pop(key) for key in ("ts", "level", "event", "trace_id", "logger")}
    ordered.update(data)
    line = json.dumps(ordered, ensure_ascii=False)
    logging.getLogger(logger_name).log(_LEVELS[level], event, extra={"trace_line": line})


def _configure() -> None:
    global _configured
    if _configured:
        return
    logger = logging.getLogger("eletric_motor")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    _configured = True
