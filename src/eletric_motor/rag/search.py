import json
import time

from pydantic import BaseModel, ConfigDict, Field
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from eletric_motor.rag.cache import cache_get, cache_key, cache_set
from eletric_motor.rag.chunk import Chunk
from eletric_motor.rag.embeddings import QUERY_PREFIX, dense_model, sparse_model
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

# Profundidade de cada braço antes da fusão RRF.
_PREFETCH = 40
# O default do cliente é 5 s; a consulta compete por CPU com o embedding local.
_QDRANT_TIMEOUT_S = 60


class SearchFilters(BaseModel, frozen=True):
    model_config = ConfigDict(extra="forbid")

    source_type: str | None = None
    manufacturer: str | None = None
    topic: str | None = None
    norm_code: str | None = None
    language: str | None = None

    def active(self) -> dict[str, str]:
        return self.model_dump(exclude_none=True)


class SearchHit(BaseModel, frozen=True):
    model_config = ConfigDict(extra="forbid")

    score: float
    chunk: Chunk


class SearchResult(BaseModel, frozen=True):
    model_config = ConfigDict(extra="forbid")

    hits: tuple[SearchHit, ...]
    dense_hits: int = Field(ge=0)
    sparse_hits: int = Field(ge=0)


def search_chunks(
    question: str,
    filters: SearchFilters | None = None,
    limit: int = 8,
    rerank: bool = False,
    use_cache: bool = True,
) -> SearchResult:
    token = bind_trace()
    started = time.perf_counter()
    settings = Settings()
    filters = filters or SearchFilters()
    fetch = max(limit, settings.rerank_candidates) if rerank else limit
    retrieved = False
    try:
        result = _search(question, filters, fetch, settings, use_cache)
        retrieved = True
        log_event(
            "retrieve.hybrid.completed",
            logger_name=__name__,
            context=TraceContext(
                span="retrieve",
                collection=settings.collection_name,
                filters=filters.active() or None,
                dense_hits=result.dense_hits,
                sparse_hits=result.sparse_hits,
                fused_hits=len(result.hits),
                latency_ms=elapsed_ms(started),
            ),
        )
        if rerank:
            result = _apply_rerank(question, result, limit, settings)
    except UnexpectedResponse as exc:
        if token is not None:
            _log_failed(exc, started)
        raise SystemExit(error_message(exc)) from exc
    except ResponseHandlingException as exc:
        if token is not None:
            _log_failed(exc, started)
        raise SystemExit(
            "Qdrant indisponível. Suba o serviço com docker compose up -d."
        ) from exc
    except SystemExit as exc:
        # SystemExit do rerank já foi registrada como rerank.failed.
        if token is not None and not retrieved:
            _log_failed(exc, started)
        raise
    except Exception as exc:
        if token is not None:
            _log_failed(exc, started)
        raise SystemExit("Não consegui consultar a coleção.") from exc
    else:
        return result
    finally:
        release_trace(token)


def _search(
    question: str,
    filters: SearchFilters,
    limit: int,
    settings: Settings,
    use_cache: bool,
) -> SearchResult:
    dense, sparse_indices, sparse_values = _question_vectors(question, use_cache)

    client = QdrantClient(url=settings.qdrant_url, timeout=_QDRANT_TIMEOUT_S)
    response = client.query_points(
        settings.collection_name,
        prefetch=[
            models.Prefetch(
                query=dense, using=settings.dense_vector_name, limit=_PREFETCH
            ),
            models.Prefetch(
                query=models.SparseVector(
                    indices=sparse_indices,
                    values=sparse_values,
                ),
                using=settings.sparse_vector_name,
                limit=_PREFETCH,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        query_filter=_qdrant_filter(filters),
        limit=limit,
        with_payload=True,
    )
    hits = tuple(
        SearchHit(score=point.score, chunk=Chunk.model_validate(point.payload))
        for point in response.points
    )
    # O cliente não expõe a contagem por braço; o log registra a profundidade pedida.
    return SearchResult(hits=hits, dense_hits=_PREFETCH, sparse_hits=_PREFETCH)


def _question_vectors(
    question: str, use_cache: bool
) -> tuple[list[float], list[int], list[float]]:
    key = cache_key("query", question)
    cached = cache_get("embedding", key, enabled=use_cache)
    if cached is not None:
        data = json.loads(cached)
        return data["dense"], data["sparse_indices"], data["sparse_values"]
    # BM25 é lexical: o esparso recebe a pergunta crua, sem o prefixo do e5.
    dense = next(iter(dense_model().embed([QUERY_PREFIX + question])))
    sparse = next(iter(sparse_model().embed([question])))
    dense_list = dense.tolist()
    sparse_indices = sparse.indices.tolist()
    sparse_values = sparse.values.tolist()
    cache_set(
        "embedding",
        key,
        json.dumps(
            {
                "dense": dense_list,
                "sparse_indices": sparse_indices,
                "sparse_values": sparse_values,
            }
        ),
        enabled=use_cache,
    )
    return dense_list, sparse_indices, sparse_values


def _apply_rerank(
    question: str,
    result: SearchResult,
    limit: int,
    settings: Settings,
) -> SearchResult:
    # Importe adiado: rerank.py importa SearchHit deste módulo.
    from eletric_motor.rag.rerank import rerank_hits

    started = time.perf_counter()
    try:
        hits = rerank_hits(question, result.hits, limit)
    except Exception as exc:
        origin = error_origin(exc)
        log_event(
            "rerank.failed",
            level="error",
            logger_name=__name__,
            context=TraceContext(
                span="rerank",
                collection=settings.collection_name,
                rerank_model=settings.reranker_model,
                rerank_candidates=len(result.hits),
                latency_ms=elapsed_ms(started),
                error_type=type(exc).__name__,
                error_message=error_message(exc),
                error_file=None if origin is None else origin[0],
                error_line=None if origin is None else origin[1],
                error_function=None if origin is None else origin[2],
            ),
        )
        raise SystemExit("Não consegui reordenar os trechos.") from exc
    log_event(
        "rerank.completed",
        logger_name=__name__,
        context=TraceContext(
            span="rerank",
            collection=settings.collection_name,
            rerank_model=settings.reranker_model,
            rerank_candidates=len(result.hits),
            fused_hits=len(hits),
            latency_ms=elapsed_ms(started),
        ),
    )
    return SearchResult(
        hits=hits,
        dense_hits=result.dense_hits,
        sparse_hits=result.sparse_hits,
    )


def _qdrant_filter(filters: SearchFilters) -> models.Filter | None:
    active = filters.active()
    if not active:
        return None
    return models.Filter(
        must=[
            models.FieldCondition(key=key, match=models.MatchValue(value=value))
            for key, value in active.items()
        ]
    )


def _log_failed(exc: BaseException, started: float) -> None:
    origin = error_origin(exc)
    log_event(
        "retrieve.hybrid.failed",
        level="error",
        logger_name=__name__,
        context=TraceContext(
            span="retrieve",
            latency_ms=elapsed_ms(started),
            error_type=type(exc).__name__,
            error_message=error_message(exc),
            error_file=None if origin is None else origin[0],
            error_line=None if origin is None else origin[1],
            error_function=None if origin is None else origin[2],
        ),
    )
