# Collection

Referência de `src/eletric_motor/rag/collection.py`. Cria ou confere a coleção híbrida no Qdrant e os índices de payload. Idempotente: rodar dez vezes tem o mesmo efeito de rodar uma.

Este arquivo é a descrição do comportamento implementado. Mudou o código, atualize este documento no mesmo passo.

## Bibliotecas

| Peça | Origem | Função neste módulo |
|---|---|---|
| `QdrantClient` | `qdrant-client` | Fala com o Qdrant por HTTP |
| `models` | `qdrant-client` | `VectorParams`, `SparseVectorParams`, `Modifier.IDF`, `PayloadSchemaType.KEYWORD` |
| `ResponseHandlingException` | `qdrant-client` | Sinal de que o Qdrant não respondeu |
| `pydantic.BaseModel` | `pydantic` v2 | `CollectionStatus`, modelo congelado |
| `trace_scope`, `bind_trace` | `eletric_motor.rag.trace` | Borda e meio da operação rastreada |

## Arquitetura

```text
init_collection                borda: abre trace_scope, monta o client
  ensure_collection            meio: bind_trace; usável por dentro de outra operação
    _ensure_collection         cria ou confere, aplica índices, emite collection.ensured
      _require_compatible      para tudo se a coleção existente é incompatível
      _ensure_payload_indexes  cria só o índice que falta
```

`store_chunks` também chama `ensure_collection` antes de gravar: a coleção é garantida no caminho da ingestão, não só no comando `init-collection`.

## Modelo

`CollectionStatus` carrega `name`, `created` e `indexes_added`. `created` é `true` só quando a coleção foi criada nesta chamada. `indexes_added` lista os índices de payload criados nesta chamada; lista vazia é gravada no evento.

## A coleção

Vetor denso `dense`, tamanho `dense_size` (1024), distância cosseno. Vetor esparso `sparse` com modificador IDF (o BM25 do Qdrant). Os nomes e o tamanho vêm de `Settings`.

Os índices de payload são os cinco de `PAYLOAD_INDEXES`: `source_type`, `manufacturer`, `topic`, `norm_code`, `language`, todos `KEYWORD`. Índice que já existe é pulado.

## Coleção incompatível

Se a coleção já existe, `_require_compatible` confere antes de seguir:

- sem vetor `dense` → `SystemExit`;
- vetor denso com tamanho ou distância diferentes → `SystemExit` com o tamanho e a distância encontrados;
- sem vetor `sparse` → `SystemExit`.

Não há migração nem recriação automática. Trocar o modelo de embedding exige outra coleção: vetor gravado com 1024 dimensões não aceita outro tamanho.

## Eventos

| Evento | Quando |
|---|---|
| `collection.init.started` | Entrada, com `collection`, `dense_size` e os nomes dos vetores |
| `collection.ensured` | Coleção criada ou conferida, com `created`, `indexes_added` e `latency_ms` |
| `collection.init.failed` | Falha de conexão ou coleção incompatível |

O detalhe de quem emite o quê (borda vs. meio, relógios diferentes) está em [Tracing.md](Tracing.md), seção "Operação da coleção".
