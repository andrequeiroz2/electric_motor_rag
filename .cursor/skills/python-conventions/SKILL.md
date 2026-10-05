---
name: python-conventions
description: >-
  Aplica as convenções Python deste repositório: Python 3.13, uv, layout src,
  Pydantic v2 e CLI. Use ao escrever, revisar ou refatorar código Python em
  eletric_motor, ou ao tipar dados, modelos e configuração.
---

# Python deste projeto

Código novo segue o layout e a CLI de `src/eletric_motor`. Dado e configuração seguem a seção Pydantic. Não reorganize o pacote sem pedido.

## Ambiente

- Python `>=3.13`, gerenciado com `uv`.
- Pacote em `src/eletric_motor`. Entrada `eletric-motor = eletric_motor:main`.
- Dependência em `pyproject.toml` só quando o código da fase em curso importa o pacote.

## Estilo

- Nomes de pacotes, módulos e identificadores em inglês. Mensagem de CLI e texto de ajuda em português.
- Anotação de tipo nas funções públicas. Dado que cruza função, módulo ou fronteira externa é modelo Pydantic v2, não `dataclass` nem `dict` solto.
- Configuração é `BaseSettings`. A referência canônica é [docs/Settings.md](../../../docs/Settings.md). O processo lê o ambiente; não há `from_env()` manual.
- CLI com `argparse` e subcomandos. Falha operacional de CLI levanta `SystemExit` com uma frase que diz o que fazer.
- Módulo pequeno, uma responsabilidade. Lógica de RAG em `eletric_motor.rag`.
- Comentário só para restrição que o código não mostra, como a dimensão do embedding presa ao modelo.

## Pydantic

Use Pydantic v2. A classe interna `Config` é da v1 e não entra em código novo.

- Dado de domínio e resultado: `BaseModel`, imutável com `frozen=True`.
- Configuração: `BaseSettings` congelado (`frozen=True`) e `SettingsConfigDict`, pacote `pydantic-settings`. O nome do campo vira a variável de ambiente (`qdrant_url` → `QDRANT_URL`). Exceção já existente: `collection_name` lê `QDRANT_COLLECTION`. O valor muda na construção, por ambiente ou argumento; a instância não muda depois.
- Restrição e metadado no `Field` por atribuição (`page: int = Field(ge=1)`). `default`, `default_factory` e `alias` ficam nessa forma para o type checker montar o `__init__`.
- Entrada externa passa por validação: construtor, `model_validate` ou `model_validate_json`. `ValidationError` aparece na fronteira; não vire default silencioso.
- Modelo de dado com `extra='forbid'`, para chave desconhecida falhar. Em `BaseSettings`, variável de ambiente desconhecida continua ignorada.
- Tipos nativos do Python 3.13 (`list[str]`, `str | None`).

`Settings` e `CollectionStatus` em `eletric_motor.rag` são a referência desses dois formatos.

```python
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings, frozen=True):
    model_config = SettingsConfigDict(extra="ignore")
    qdrant_url: str = "http://localhost:6333"

class CollectionStatus(BaseModel, frozen=True):
    name: str
    created: bool
    indexes_added: tuple[str, ...] = Field(default_factory=tuple)
```

## Exemplo de fronteira

```python
def ensure_collection(client: QdrantClient, settings: Settings) -> CollectionStatus:
    ...
```

A função de biblioteca devolve um resultado. Quem imprime para o usuário é o comando em `main`.
