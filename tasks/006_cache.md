# 006 — Cache Redis de embedding e de resposta

Task de implementação. Adiciona Redis ao lado do Qdrant e cacheia duas coisas: o embedding da pergunta (a busca não reembeda pergunta repetida) e a resposta pronta (pergunta repetida não paga rerank nem API). Esta task não muda a coleção, não reingere PDF e não usa MCP.

Cada fase nasce pendente. Ao terminar a implementação e a verificação descritas nela, o status nesta tabela passa a `concluída`. Código escrito sem essa verificação permanece `pendente`. A fase seguinte só começa com a anterior `concluída`.

| Fase | Entrega | Status |
|---|---|---|
| 1 | Redis no compose, dependência, settings e módulo `cache.py` | concluída |
| 2 | Cache do embedding da pergunta na busca | concluída |
| 3 | Cache da resposta no `answer` e flags na CLI | concluída |

## Regras comuns às fases

- **Cache é otimização, não infraestrutura crítica**: Redis fora do ar não derruba busca nem resposta. Emite `cache.unavailable` em nível warning uma vez por processo e segue sem cache. Diferente do reranker, aqui o fallback é o caminho normal.
- Chave é SHA-256 dos dados que definem o resultado: na resposta, pergunta + filtros + limite + rerank + modelo; no embedding, o texto da pergunta.
- TTL único configurável (`CACHE_TTL_S`, padrão 24 h). Resposta cacheada pode ficar velha se um PDF for reingerido; o TTL é o limite dessa janela.
- O JSON de trace não leva chave de cache completa nem valor cacheado: leva `cache_scope` (`embedding` ou `answer`) e `cache_hit` (bool).
- Resposta vinda do cache **não** emite `retrieve.*` nem `generate.*`: o único evento é o `cache.lookup` com hit. Emitir `generate.answered` sem chamada ao LLM seria mentira no trace.
- `query` e `answer` ganham `--no-cache` para inspeção sem cache.

## Fase 1 — Infraestrutura

Serviço `redis` no `compose.yaml` (imagem `redis:7-alpine`, porta 6379, volume). Dependência `redis` no `pyproject.toml`. `Settings` ganha `redis_url` (padrão `redis://localhost:6379`), `cache_ttl_s` (padrão 86400, `>= 1`) e `cache_enabled` (padrão `true`).

`rag/cache.py`: cliente cacheado por processo (timeout de conexão de 1 s — Redis parado não pode segurar a CLI), `cache_get`/`cache_set` com os eventos `cache.lookup` e `cache.unavailable`, e `cache_key(*parts)` com o SHA-256. Depois de uma falha de conexão, o módulo desliga o cache pelo resto do processo sem repetir o warning.

Verificação: `docker compose up -d` sobe os dois serviços. Um `cache_set`/`cache_get` em Python ida e volta. Com o Redis parado, o get devolve `None`, emite um warning só e não levanta exceção.

## Fase 2 — Cache do embedding da pergunta

`_search` consulta o cache antes de embedar a pergunta. Miss: embeda e grava (denso como lista, esparso como índices + valores). Hit: monta os vetores do JSON e pula o modelo.

Verificação: duas execuções do mesmo `query` — a segunda tem `cache.lookup` com `cache_scope="embedding"` e `cache_hit=true`, e o `retrieve.hybrid.completed` sai com latência visivelmente menor.

## Fase 3 — Cache da resposta

`answer_question` consulta o cache antes de buscar. Hit: devolve o `AnswerResult` do JSON e encerra — sem retrieve, sem rerank, sem LLM. Miss: fluxo normal e grava o resultado no fim.

Verificação: duas execuções do mesmo `answer` — a segunda só emite `cache.lookup` com `cache_scope="answer"`, `cache_hit=true`, e responde em fração de segundo. `--no-cache` força o fluxo completo.

## Critério de pronto desta task

As três linhas da tabela de fases estão `concluída`. Redis parado não quebra `query` nem `answer`. `docs/Tracing.md`, `docs/Settings.md`, novo `docs/Cache.md`, README e o skill `rag-motors` refletem o cache.
