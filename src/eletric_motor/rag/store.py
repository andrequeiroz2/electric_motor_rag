import time
import uuid
from itertools import batched

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from eletric_motor.rag.chunk import Chunk
from eletric_motor.rag.embeddings import PASSAGE_PREFIX, dense_model, sparse_model
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

_UPSERT_BATCH = 64
# O default do cliente é 5 s; o upsert com wait=true compete por CPU com o embedding.
_QDRANT_TIMEOUT_S = 60


class StoreResult(BaseModel, frozen=True):
    model_config = ConfigDict(extra="forbid")

    points_written: int = Field(ge=0)
    points_existing: int = Field(ge=0)
    points_updated: int = Field(ge=0)


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
                points_updated=result.points_updated,
                latency_ms=elapsed_ms(started),
            ),
        )
        return result
    finally:
        release_trace(token)


def _store(chunks: tuple[Chunk, ...]) -> StoreResult:
    settings = Settings()
    ids = [_point_id(chunk) for chunk in chunks]
    client = QdrantClient(url=settings.qdrant_url, timeout=_QDRANT_TIMEOUT_S)
    ensure_collection(client, settings)
    found = client.retrieve(
        settings.collection_name, ids, with_payload=True, with_vectors=False
    )
    existing = {str(point.id): point.payload for point in found}
    # Só embeda o que falta: reingestão de documento igual não roda o modelo,
    # e uma falha no meio retoma de onde parou.
    todo = [
        (chunk, point_id)
        for chunk, point_id in zip(chunks, ids, strict=True)
        if point_id not in existing
    ]
    # Upsert a cada lote: a conexão não fica minutos parada durante o embedding.
    for batch in batched(todo, _UPSERT_BATCH):
        points = _points(
            tuple(chunk for chunk, _ in batch),
            [point_id for _, point_id in batch],
            settings,
        )
        client.upsert(settings.collection_name, points)
    updated = _refresh_payloads(client, settings, chunks, ids, existing)
    _delete_stale(client, settings, chunks[0].document_id, ids)
    return StoreResult(
        points_written=len(todo),
        points_existing=len(found),
        points_updated=updated,
    )


# O metadado de um trecho inalterado também evolui (ex.: hierarquia de seções
# corrigida); set_payload atualiza sem reembedar o vetor.
def _refresh_payloads(
    client: QdrantClient,
    settings: Settings,
    chunks: tuple[Chunk, ...],
    ids: list[str],
    existing: dict[str, dict],
) -> int:
    updated = 0
    for chunk, point_id in zip(chunks, ids, strict=True):
        payload = existing.get(point_id)
        if payload is None:
            continue
        new_payload = chunk.model_dump(mode="json", exclude_none=True)
        if payload != new_payload:
            client.set_payload(settings.collection_name, new_payload, points=[point_id])
            updated += 1
    return updated


# Extração nova muda o hash do trecho: pontos do documento fora do lote atual
# são restos de uma extração anterior e saem da coleção.
def _delete_stale(
    client: QdrantClient, settings: Settings, document_id: str, ids: list[str]
) -> None:
    client.delete(
        collection_name=settings.collection_name,
        points_selector=models.Filter(
            must=[
                models.FieldCondition(
                    key="document_id", match=models.MatchValue(value=document_id)
                )
            ],
            must_not=[models.HasIdCondition(has_id=ids)],
        ),
    )


def _points(
    chunks: tuple[Chunk, ...],
    ids: list[str],
    settings: Settings,
) -> list[models.PointStruct]:
    # BM25 é lexical: o esparso recebe o texto cru, sem o prefixo do e5.
    dense = list(dense_model().embed([PASSAGE_PREFIX + c.content for c in chunks]))
    sparse = list(sparse_model().embed([c.content for c in chunks]))
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
