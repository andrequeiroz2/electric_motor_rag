# Rerank

Referência de `src/eletric_motor/rag/rerank.py`. Reordena os trechos da busca híbrida com um cross-encoder antes do corte final. O trecho certo sobe sem precisar de limite alto.

Este arquivo é a descrição do comportamento implementado. Mudou o código, atualize este documento no mesmo passo.

## Bibliotecas

| Peça | Origem | Função neste módulo |
|---|---|---|
| `TextCrossEncoder` | `fastembed.rerank.cross_encoder` | O cross-encoder, via onnxruntime |
| `functools.cache` | biblioteca padrão | Uma instância do modelo por processo |
| `SearchHit` | [Search.md](Search.md) | O que entra e o que sai |

## Por que existe

A busca híbrida usa bi-encoders: pergunta e trecho viram vetores separados e a relevância é aproximada. O cross-encoder recebe o par (pergunta, trecho) como entrada única e devolve uma nota por par — mais preciso, mas uma inferência por par, inviável na coleção toda. Por isso o desenho em dois estágios: a fusão RRF garante a abrangência (pool de `rerank_candidates`, padrão 24) e o cross-encoder garante a precisão (corte no `limit`).

## Modelo

`jinaai/jina-reranker-v2-base-multilingual`, multilíngue como o acervo (PT/EN/ES). O roadmap original pedia `bge-reranker-v2-m3`, que o fastembed não suporta — usá-lo puxaria `sentence-transformers` + PyTorch e quebraria o padrão de ONNX puro. A decisão está em `tasks/005_reranker.md`.

O loader segue o padrão de [Embeddings.md](Embeddings.md): `@cache`, arena de CPU desligada e `EMBEDDING_THREADS` respeitado. O primeiro uso baixa ~1,1 GB.

## rerank_hits

Extrai o `content` de cada hit (tabela leva o título da seção no início, o que ajuda o cross-encoder), pontua todos contra a pergunta, ordena decrescente e devolve os `limit` melhores. **O score do hit passa a ser a nota do cross-encoder** — um logit, não mais o score RRF; valores negativos são normais.

## Falhas

Quem emite `rerank.completed` e `rerank.failed` é `search.py`, que também decide o `SystemExit`. Este módulo só levanta a exceção original. Não há fallback silencioso para a ordem RRF: reranker quebrado é falha visível, não degradação escondida.

## Custo

Cada par é uma inferência: 24 candidatos levam ~13 s em CPU. Os botões de ajuste são `RERANK_CANDIDATES` (pool menor, mais rápido), `--no-rerank` no `answer` e o `query` sem `--rerank` para inspeção crua.
