# Store

Referência de `src/eletric_motor/rag/store.py`. Grava os chunks na coleção como pontos com os dois vetores e o payload. Idempotente e retomável: reingerir o mesmo documento não duplica nem reembeda, e uma falha no meio retoma de onde parou.

Este arquivo é a descrição do comportamento implementado. Mudou o código, atualize este documento no mesmo passo.

## Bibliotecas

| Peça | Origem | Função neste módulo |
|---|---|---|
| `QdrantClient`, `models` | `qdrant-client` | Retrieve, upsert, set_payload e delete por filtro |
| `itertools.batched` | biblioteca padrão | Lotes de 64 pontos |
| `uuid.uuid5` | biblioteca padrão | Id determinístico do ponto |
| `numpy` | `numpy` | Checagem de vetor finito |
| `dense_model`, `sparse_model` | [Embeddings.md](Embeddings.md) | Os dois vetores de cada chunk |
| `ensure_collection` | [Collection.md](Collection.md) | Garante a coleção antes de gravar |

## Arquitetura

```text
store_chunks               bind_trace, eventos e SystemExit em português
  _store
    ensure_collection      coleção garantida no caminho da gravação
    retrieve               quais ids já existem (payload, sem vetor)
    laço em lotes de 64    embeda só o que falta + upsert por lote
    _refresh_payloads      set_payload nos existentes cujo payload mudou
    _delete_stale          remove pontos do documento fora do lote atual
```

## Id do ponto

`uuid5(NAMESPACE_URL, "{document_id}:{content_hash}")`. O id deriva do documento e do hash do trecho: reingestão sobrescreve o mesmo ponto em vez de criar outro. Trechos idênticos no mesmo documento têm o mesmo hash e colapsam num ponto só (ver [Chunk.md](Chunk.md)).

## Só embeda o que falta

Antes de embedar, `_store` consulta quais ids já existem. Reingestão de documento igual não roda o modelo — é o que torna a segunda execução rápida e barata. O embedding e o upsert andam intercalados em lotes de 64: a conexão não fica minutos parada durante o embedding, e se o processo morrer no meio, os lotes já gravados não se perdem — a próxima execução retoma do primeiro lote que falta.

O timeout do cliente é 60 s (o default de 5 s estourava: o upsert com `wait=true` compete por CPU com o embedding local).

## Refresh de payload

O metadado de um trecho inalterado também evolui — a correção da hierarquia de seções do manual atualizou 142 pontos já gravados. `_refresh_payloads` compara o payload gravado com o atual e aplica `set_payload` só onde mudou, sem reembedar o vetor. Esses pontos contam como `points_updated`.

## Limpeza de restos

Extração nova muda o hash dos trechos. `_delete_stale` remove os pontos do mesmo `document_id` cujo id não está no lote atual (filtro `must` no documento + `must_not` nos ids atuais): reingerir após mudar a extração não deixa restos da versão anterior na coleção.

## Vetor finito

NaN ou inf no vetor vira JSON inválido e o Qdrant rejeita o lote inteiro com 400. `_require_finite` confere os dois vetores antes do upsert e falha com o hash do chunk culpado.

## Modelo e eventos

`StoreResult`: `points_written` (novos), `points_existing` (já estavam lá), `points_updated` (payload atualizado sem reembedar).

| Evento | Quando |
|---|---|
| `ingest.document.stored` | Chunks gravados, com as três contagens e `latency_ms` |
| `ingest.document.failed` | A gravação falhou (Qdrant fora, vetor não finito, erro interno) |
