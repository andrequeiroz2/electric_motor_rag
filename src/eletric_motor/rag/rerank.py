from functools import cache

from fastembed.rerank.cross_encoder import TextCrossEncoder

from eletric_motor.rag.search import SearchHit
from eletric_motor.rag.settings import Settings

# Mesmo motivo de embeddings.py: a arena do onnxruntime não devolve memória ao SO.
_ARENA_OFF = {"enable_cpu_mem_arena": False}


@cache
def reranker_model() -> TextCrossEncoder:
    return TextCrossEncoder(
        model_name=Settings().reranker_model, **_ARENA_OFF, **_threads()
    )


def rerank_hits(
    question: str,
    hits: tuple[SearchHit, ...],
    limit: int,
) -> tuple[SearchHit, ...]:
    """Re-score hits with the cross-encoder and keep the best `limit`."""
    documents = [hit.chunk.content for hit in hits]
    scores = list(reranker_model().rerank(question, documents))
    ranked = sorted(zip(scores, hits), key=lambda pair: pair[0], reverse=True)
    return tuple(
        SearchHit(score=float(score), chunk=hit.chunk) for score, hit in ranked[:limit]
    )


def _threads() -> dict[str, int]:
    threads = Settings().embedding_threads
    return {} if threads is None else {"threads": threads}
