from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Dimensão de intfloat/multilingual-e5-large. Trocar o modelo exige outra coleção.
DENSE_SIZE = 1024

PAYLOAD_INDEXES = (
    "source_type",
    "manufacturer",
    "topic",
    "norm_code",
    "language",
)


class Settings(BaseSettings, frozen=True):
    model_config = SettingsConfigDict(extra="ignore", validate_by_name=True, env_file=".env")

    qdrant_url: str = "http://localhost:6333"
    collection_name: str = Field(default="eletric_motor", validation_alias="QDRANT_COLLECTION")
    dense_vector_name: str = "dense"
    sparse_vector_name: str = "sparse"
    dense_size: int = Field(default=DENSE_SIZE, ge=1)
    # None: o onnxruntime usa todos os núcleos. Limite baixo mantém a máquina responsiva.
    embedding_threads: int | None = Field(default=None, ge=1)
    # O default do fastembed é /tmp/fastembed_cache, que some no reboot e força
    # re-download dos ~3 GB de modelos. Aqui o cache é persistente.
    model_cache_dir: Path = Path.home() / ".cache" / "fastembed"
    # Chave da OpenAI. Nunca vai para o trace nem para a frase da CLI.
    openai_api_key: SecretStr | None = None
    llm_model: str = "gpt-4o"
    # Teto de tokens de contexto no prompt. A cota TPM da org é o limite real:
    # 16 trechos com tabelas grandes passaram de 50k e tomaram 429.
    llm_context_tokens: int = Field(default=12000, ge=1)
    # Cross-encoder local que reordena os trechos fundidos antes do corte.
    reranker_model: str = "jinaai/jina-reranker-v2-base-multilingual"
    rerank_candidates: int = Field(default=24, ge=1)
    # Cache de embedding e de resposta. Redis fora do ar não derruba a CLI.
    redis_url: str = "redis://localhost:6379"
    cache_ttl_s: int = Field(default=86400, ge=1)
    cache_enabled: bool = True
