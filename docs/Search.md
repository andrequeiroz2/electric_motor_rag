# Search

Referência de `src/eletric_motor/rag/search.py`. Busca híbrida na coleção: prefetch denso e esparso, fusão RRF, filtro de payload opcional e rerank opcional. É a metade "pergunta" do RAG — a outra metade é [Answer.md](Answer.md).

Este arquivo é a descrição do comportamento implementado. Mudou o código, atualize este documento no mesmo passo.

## Bibliotecas

| Peça | Origem | Função neste módulo |
|---|---|---|
| `QdrantClient`, `models` | `qdrant-client` | `Prefetch`, `FusionQuery` RRF, filtro de payload |
| `dense_model`, `sparse_model` | [Embeddings.md](Embeddings.md) | Vetores da pergunta |
| `Chunk` | [Chunk.md](Chunk.md) | O payload validado de volta |
| `rerank_hits` | [Rerank.md](Rerank.md) | Reordenação opcional (importe adiado) |

## Arquitetura

```text
search_chunks                bind_trace, eventos, SystemExit em português
  _search
    embed da pergunta        denso com "query: ", esparso com o texto cru
    query_points             prefetch 40 denso + 40 esparso, fusão RRF
    filtro de payload        só quando a pergunta pede
  _apply_rerank              opcional: cross-encoder nos candidatos
```

## Modelos

`SearchFilters`: os cinco metadados indexados (`source_type`, `manufacturer`, `topic`, `norm_code`, `language`), todos opcionais. `active()` devolve só os preenchidos — filtro vazio nem vira `Filter` no Qdrant.

`SearchHit`: `score` + `Chunk`. `SearchResult`: a tupla de hits e a profundidade pedida a cada braço (`dense_hits`, `sparse_hits` — o cliente não expõe a contagem real por braço, então o log registra a profundidade pedida).

## A consulta

Cada braço faz prefetch de 40 e a fusão RRF ordena o resultado. O denso recebe a pergunta com o prefixo `query: ` do e5; o esparso recebe o texto cru (BM25 é lexical). O timeout do cliente é 60 s: a consulta compete por CPU com o embedding local.

O payload de cada ponto é validado com `Chunk.model_validate` — ponto com payload fora do contrato falha aqui, não mais adiante.

## Rerank

Com `rerank=True`, a busca pede `max(limit, rerank_candidates)` trechos fundidos e `_apply_rerank` reordena com o cross-encoder, cortando no `limit`. O score do hit passa a ser a nota do cross-encoder. Detalhes em [Rerank.md](Rerank.md).

O importe de `rerank_hits` é adiado para dentro da função: `rerank.py` importa `SearchHit` deste módulo, e o importe direto fecharia um ciclo.

## Falhas

| Falha | Vira |
|---|---|
| `UnexpectedResponse` (Qdrant recusou) | `SystemExit` com a mensagem curta do erro |
| `ResponseHandlingException` (Qdrant fora) | `SystemExit` orientando a subir o Docker |
| `SystemExit` do rerank | sobe; quem registrou foi o `rerank.failed` |
| Qualquer outra | `SystemExit` "Não consegui consultar a coleção." |

## Eventos

| Evento | Quando |
|---|---|
| `retrieve.hybrid.completed` | Fusão concluída — emitido logo após a busca, antes do rerank, para a latência e a contagem serem as do retrieve |
| `retrieve.hybrid.failed` | A busca falhou |
| `rerank.completed` / `rerank.failed` | Ver [Rerank.md](Rerank.md) |

Com `rerank` ligado, o `except SystemExit` não repete o `retrieve.hybrid.failed`: a busca já tinha sido registrada como sucesso.
