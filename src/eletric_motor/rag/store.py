import time
import uuid
from functools import cache
from itertools import batched

import numpy as np
from fastembed import SparseTextEmbedding, TextEmbedding
from pydantic import BaseModel, ConfigDict, Field
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from eletric_motor.rag.chunk import Chunk
from eletric_motor.rag.collection import ensure_collection
from eletric_motor.rag.settings import Settings
from eletric_motor.rag.trace import (
    TraceContext,
    bind_trace,
    elapsed_ms,
    error_message,
    error_origin,
    log_event,
    release_trace,
)

# Dimensão presa a intfloat/multilingual-e5-large; trocar o modelo exige outra coleção.
_DENSE_MODEL = "intfloat/multilingual-e5-large"
_SPARSE_MODEL = "Qdrant/bm25"
# O e5 exige o prefixo "passage: " em documentos ("query: " nas consultas, fase de busca).
_PASSAGE_PREFIX = "passage: "
_UPSERT_BATCH = 64
# O default do cliente é 5 s; o upsert com wait=true compete por CPU com o embedding.
_QDRANT_TIMEOUT_S = 60


class StoreResult(BaseModel, frozen=True):
    model_config = ConfigDict(extra="forbid")

    points_written: int = Field(ge=0)
    points_existing: int = Field(ge=0)


def store_chunks(chunks: tuple[Chunk, ...]) -> StoreResult:
    token = bind_trace()
    started = time.perf_counter()
    document_id = chunks[0].document_id if chunks else ""
    try:
        result = _store(chunks)
    except UnexpectedResponse as exc:
        if token is not None:
            _log_failed(document_id, exc, started)
        raise SystemExit(error_message(exc)) from exc
    except ResponseHandlingException as exc:
        if token is not None:
            _log_failed(document_id, exc, started)
        raise SystemExit(
            "Qdrant indisponível. Suba o serviço com docker compose up -d."
        ) from exc
    except SystemExit as exc:
        if token is not None:
            _log_failed(document_id, exc, started)
        raise
    except Exception as exc:
        if token is not None:
            _log_failed(document_id, exc, started)
        raise SystemExit(f"Não consegui gravar os chunks de {document_id}.") from exc
    else:
        log_event(
            "ingest.document.stored",
            logger_name=__name__,
            context=TraceContext(
                document_id=document_id,
                points_written=result.points_written,
                points_existing=result.points_existing,
                latency_ms=elapsed_ms(started),
            ),
        )
        return result
    finally:
        release_trace(token)


def _store(chunks: tuple[Chunk, ...]) -> StoreResult:
    settings = Settings()
    ids = [_point_id(chunk) for chunk in chunks]
    # O embedding leva minutos; a conexão com o Qdrant só abre depois dele,
    # para o upsert não reusar uma conexão keep-alive que o servidor já fechou.
    points = _points(chunks, ids, settings)

    client = QdrantClient(url=settings.qdrant_url, timeout=_QDRANT_TIMEOUT_S)
    ensure_collection(client, settings)
    found = client.retrieve(
        settings.collection_name, ids, with_payload=False, with_vectors=False
    )
    for batch in batched(points, _UPSERT_BATCH):
        # upsert exige list: tupla pula a conversão para PointsList no cliente
        # e vira corpo de streaming inválido no httpx (Qdrant responde 400).
        client.upsert(settings.collection_name, list(batch))
    return StoreResult(
        points_written=len(points) - len(found),
        points_existing=len(found),
    )


def _points(
    chunks: tuple[Chunk, ...],
    ids: list[str],
    settings: Settings,
) -> list[models.PointStruct]:
    # BM25 é lexical: o esparso recebe o texto cru, sem o prefixo do e5.
    dense = list(_dense_model().embed([_PASSAGE_PREFIX + c.content for c in chunks]))
    sparse = list(_sparse_model().embed([c.content for c in chunks]))
    for chunk, dense_vector, sparse_vector in zip(chunks, dense, sparse, strict=True):
        _require_finite(chunk, dense_vector, sparse_vector.values)
    return [
        models.PointStruct(
            id=point_id,
            vector={
                settings.dense_vector_name: dense_vector.tolist(),
                settings.sparse_vector_name: models.SparseVector(
                    indices=sparse_vector.indices.tolist(),
                    values=sparse_vector.values.tolist(),
                ),
            },
            payload=chunk.model_dump(mode="json", exclude_none=True),
        )
        for point_id, chunk, dense_vector, sparse_vector in zip(
            ids, chunks, dense, sparse, strict=True
        )
    ]


# NaN ou inf no vetor vira JSON inválido e o Qdrant rejeita o lote inteiro com 400.
def _require_finite(chunk: Chunk, dense: np.ndarray, sparse_values: np.ndarray) -> None:
    if not np.isfinite(dense).all() or not np.isfinite(sparse_values).all():
        raise ValueError(f"embedding não finito no chunk {chunk.content_hash[:12]}")


# O id deriva do documento e do hash do trecho: reingestão sobrescreve, não duplica.
def _point_id(chunk: Chunk) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{chunk.document_id}:{chunk.content_hash}"))


@cache
def _dense_model() -> TextEmbedding:
    return TextEmbedding(model_name=_DENSE_MODEL)


@cache
def _sparse_model() -> SparseTextEmbedding:
    return SparseTextEmbedding(model_name=_SPARSE_MODEL)


def _log_failed(document_id: str, exc: BaseException, started: float) -> None:
    origin = error_origin(exc)
    log_event(
        "ingest.document.failed",
        level="error",
        logger_name=__name__,
        context=TraceContext(
            document_id=document_id,
            latency_ms=elapsed_ms(started),
            error_type=type(exc).__name__,
            error_message=error_message(exc),
            error_file=None if origin is None else origin[0],
            error_line=None if origin is None else origin[1],
            error_function=None if origin is None else origin[2],
        ),
    )
