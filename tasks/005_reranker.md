# 005 — Reranker dos trechos recuperados

Task de implementação. Reordena os trechos da busca híbrida com um cross-encoder antes de mandar ao LLM, para subir o trecho certo sem precisar de limite alto. Esta task não usa Redis nem MCP, não muda a coleção e não reingere PDF.

O roadmap do skill pedia `bge-reranker-v2-m3`. O fastembed (0.8.1, versão mais recente) não suporta esse modelo; usá-lo exigiria `sentence-transformers` + PyTorch, quebrando o padrão de ONNX puro. **Decisão**: `jinaai/jina-reranker-v2-base-multilingual` via `fastembed.rerank.cross_encoder.TextCrossEncoder` — multilíngue (PT/EN/ES, como o acervo), mesmo runtime onnxruntime, nenhuma dependência nova.

Cada fase nasce pendente. Ao terminar a implementação e a verificação descritas nela, o status nesta tabela passa a `concluída`. Código escrito sem essa verificação permanece `pendente`. A fase seguinte só começa com a anterior `concluída`.

| Fase | Entrega | Status |
|---|---|---|
| 1 | Módulo `rerank.py` e campos de configuração | concluída |
| 2 | Integração na busca e flags na CLI | concluída |
| 3 | Trace `rerank.completed` / `rerank.failed` e regressão de qualidade | concluída |

## Regras comuns às fases

- O reranker roda depois da fusão RRF: a busca pede `rerank_candidates` trechos fundidos (padrão 24), o cross-encoder pontua cada um contra a pergunta e os `limit` melhores seguem.
- O loader segue o padrão de `embeddings.py`: `@cache`, arena de CPU desligada, `EMBEDDING_THREADS` respeitado.
- O score do hit passa a ser o do cross-encoder após o rerank.
- Falha do reranker emite `rerank.failed` e sobe como `SystemExit` com frase em português, como no retrieve. Sem fallback silencioso.
- `query` ganha `--rerank` (desligado por padrão: o `query` é a ferramenta de inspeção da busca crua). `answer` reranqueia por padrão e ganha `--no-rerank` para desligar.
- Eventos novos entram na tabela de `docs/Tracing.md` antes de aparecer no código. Campos novos entram em `TraceContext` e na tabela de campos no mesmo passo.

## Fase 1 — Módulo e configuração

`rag/rerank.py` com o loader cacheado do `TextCrossEncoder` e `rerank_hits(question, hits, limit)`, que devolve os hits reordenados com o score do cross-encoder.

`Settings` ganha `reranker_model` (default `jinaai/jina-reranker-v2-base-multilingual`) e `rerank_candidates` (default 24, `>= 1`). Tabela de campos de `docs/Settings.md` atualizada no mesmo passo.

Verificação: importar `rerank_hits` e reranquear uma lista pequena em Python; a ordem muda conforme a relevância e o tamanho respeita `limit`. O primeiro uso baixa o modelo (~1,1 GB).

## Fase 2 — Integração e CLI

`search_chunks` ganha `rerank: bool = False`. Ligado, busca `rerank_candidates` trechos e devolve os `limit` melhores após o cross-encoder. `query --rerank` e `answer` (padrão ligado, `--no-rerank` desliga).

Verificação: `query "qual a corrente de partida do W22" --rerank --limit 8` coloca `3.11 Placas de Identificação` no top-8 (com RRF puro e limite 8 ele ficava de fora).

## Fase 3 — Trace e regressão

`rerank.completed` leva `span="rerank"`, `rerank_model`, `rerank_candidates`, `fused_hits` (trechos devolvidos) e `latency_ms`, no mesmo `trace_id` do retrieve. `rerank.failed` leva os campos de erro de sempre.

Verificação: uma execução de `answer` emite `retrieve.hybrid.completed`, `rerank.completed` e `generate.answered` com o mesmo `trace_id`. A resposta da pergunta de regressão cita a placa de identificação sem precisar de `--limit` alto.

## Critério de pronto desta task

As três linhas da tabela de fases estão `concluída`. O `answer` reranqueia por padrão. `docs/Tracing.md`, `docs/Settings.md`, o skill `rag-motors` e o README refletem o reranker.
