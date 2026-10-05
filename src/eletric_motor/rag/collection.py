import time

from pydantic import BaseModel, ConfigDict, Field
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import ResponseHandlingException

from eletric_motor.rag.settings import PAYLOAD_INDEXES, Settings
from eletric_motor.rag.trace import (
    TraceContext,
    bind_trace,
    elapsed_ms,
    error_message,
    error_origin,
    log_event,
    release_trace,
    trace_scope,
)


class CollectionStatus(BaseModel, frozen=True):
    model_config = ConfigDict(extra="forbid")

    name: str
    created: bool
    indexes_added: tuple[str, ...] = Field(default_factory=tuple)


def ensure_collection(client: QdrantClient, settings: Settings) -> CollectionStatus:
    token = bind_trace()
    started = time.perf_counter()
    if token is not None:
        _log_started(settings)
    try:
        return _ensure_collection(client, settings, started)
    except (ResponseHandlingException, SystemExit) as exc:
        if token is not None:
            _log_failed(settings.collection_name, exc, started)
        raise
    finally:
        release_trace(token)


def _ensure_collection(
    client: QdrantClient,
    settings: Settings,
    started: float,
) -> CollectionStatus:
    created = False
    if not client.collection_exists(settings.collection_name):
        client.create_collection(
            collection_name=settings.collection_name,
            vectors_config={
                settings.dense_vector_name: models.VectorParams(
                    size=settings.dense_size,
                    distance=models.Distance.COSINE,
                ),
            },
            sparse_vectors_config={
                settings.sparse_vector_name: models.SparseVectorParams(
                    modifier=models.Modifier.IDF,
                ),
            },
        )
        created = True
    else:
        _require_compatible(client, settings)

    indexes_added = _ensure_payload_indexes(client, settings.collection_name)
    status = CollectionStatus(
        name=settings.collection_name,
        created=created,
        indexes_added=indexes_added,
    )
    log_event(
        "collection.ensured",
        logger_name=__name__,
        context=TraceContext(
            collection=status.name,
            created=status.created,
            indexes_added=status.indexes_added,
            latency_ms=elapsed_ms(started),
        ),
    )
    return status


def init_collection() -> CollectionStatus:
    with trace_scope():
        settings = Settings()
        started = time.perf_counter()
        _log_started(settings)
        try:
            client = QdrantClient(url=settings.qdrant_url)
            return ensure_collection(client, settings)
        except ResponseHandlingException as exc:
            _log_failed(settings.collection_name, exc, started)
            raise SystemExit(
                f"Qdrant indisponível em {settings.qdrant_url}. Suba o serviço com docker compose up -d."
            ) from exc
        except SystemExit as exc:
            _log_failed(settings.collection_name, exc, started)
            raise


def _log_started(settings: Settings) -> None:
    log_event(
        "collection.init.started",
        logger_name=__name__,
        context=TraceContext(
            collection=settings.collection_name,
            dense_size=settings.dense_size,
            dense_vector_name=settings.dense_vector_name,
            sparse_vector_name=settings.sparse_vector_name,
        ),
    )


def _log_failed(collection: str, exc: BaseException, started: float) -> None:
    origin = error_origin(exc)
    log_event(
        "collection.init.failed",
        level="error",
        logger_name=__name__,
        context=TraceContext(
            collection=collection,
            latency_ms=elapsed_ms(started),
            error_type=type(exc).__name__,
            error_message=error_message(exc),
            error_file=None if origin is None else origin[0],
            error_line=None if origin is None else origin[1],
            error_function=None if origin is None else origin[2],
        ),
    )


def _require_compatible(client: QdrantClient, settings: Settings) -> None:
    params = client.get_collection(settings.collection_name).config.params
    vectors = params.vectors
    if not isinstance(vectors, dict) or settings.dense_vector_name not in vectors:
        raise SystemExit(
            f"A coleção {settings.collection_name} não tem o vetor {settings.dense_vector_name}."
        )
    dense = vectors[settings.dense_vector_name]
    if dense.size != settings.dense_size or dense.distance != models.Distance.COSINE:
        raise SystemExit(
            f"A coleção {settings.collection_name} já existe com vetor denso incompatível "
            f"(tamanho {dense.size}, distância {dense.distance})."
        )
    sparse = params.sparse_vectors or {}
    if settings.sparse_vector_name not in sparse:
        raise SystemExit(
            f"A coleção {settings.collection_name} não tem o vetor esparso {settings.sparse_vector_name}."
        )


def _ensure_payload_indexes(client: QdrantClient, collection_name: str) -> tuple[str, ...]:
    existing = client.get_collection(collection_name).payload_schema
    added: list[str] = []
    for field in PAYLOAD_INDEXES:
        if field in existing:
            continue
        client.create_payload_index(
            collection_name=collection_name,
            field_name=field,
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
        added.append(field)
    return tuple(added)
