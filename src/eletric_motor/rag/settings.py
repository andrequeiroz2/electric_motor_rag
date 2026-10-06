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
    # Chave da OpenAI. Nunca vai para o trace nem para a frase da CLI.
    openai_api_key: SecretStr | None = None
    llm_model: str = "gpt-4o"
    # Cross-encoder local que reordena os trechos fundidos antes do corte.
    reranker_model: str = "jinaai/jina-reranker-v2-base-multilingual"
    rerank_candidates: int = Field(default=24, ge=1)
