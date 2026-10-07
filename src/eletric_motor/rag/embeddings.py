from functools import cache

from fastembed import SparseTextEmbedding, TextEmbedding

from eletric_motor.rag.settings import Settings

# Dimensão presa a intfloat/multilingual-e5-large; trocar o modelo exige outra coleção.
DENSE_MODEL = "intfloat/multilingual-e5-large"
SPARSE_MODEL = "Qdrant/bm25"
# O e5 exige o prefixo "passage: " em documentos e "query: " em consultas.
PASSAGE_PREFIX = "passage: "
QUERY_PREFIX = "query: "


# A arena de memória do onnxruntime acumula blocos por formato de entrada e não
# devolve ao SO: 535 chunks de tamanhos variados levaram o processo a 27 GB (OOM).
_ARENA_OFF = {"enable_cpu_mem_arena": False}


@cache
def dense_model() -> TextEmbedding:
    return TextEmbedding(model_name=DENSE_MODEL, **_ARENA_OFF, **_options())


@cache
def sparse_model() -> SparseTextEmbedding:
    return SparseTextEmbedding(model_name=SPARSE_MODEL, **_ARENA_OFF, **_options())


def _options() -> dict[str, int | str]:
    settings = Settings()
    options: dict[str, int | str] = {"cache_dir": str(settings.model_cache_dir)}
    if settings.embedding_threads is not None:
        options["threads"] = settings.embedding_threads
    return options
