# Cache

Referência de `src/eletric_motor/rag/cache.py`. Cache Redis de dois resultados caros: o embedding da pergunta e a resposta pronta do LLM. Cache é otimização, não infraestrutura crítica: Redis fora do ar não derruba busca nem resposta.

Este arquivo é a descrição do comportamento implementado. Mudou o código, atualize este documento no mesmo passo.

## Bibliotecas

| Peça | Origem | Função neste módulo |
|---|---|---|
| `redis.Redis` | `redis` (redis-py) | Cliente do Redis |
| `hashlib` | biblioteca padrão | SHA-256 da chave |
| `functools.cache` | biblioteca padrão | Um cliente por processo |

## Arquitetura

```text
cache_key(*parts)        SHA-256 das partes, separadas por \x1f
cache_get(scope, key)    busca "{scope}:{key}" e emite cache.lookup
cache_set(scope, key)    grava com SETEX e o TTL de Settings
_client()                timeouts de 1 s: Redis parado não segura a CLI
_mark_unavailable        warning único e cache desligado no processo
```

## O que é cacheado

| Escopo | Onde | Chave | Valor |
|---|---|---|---|
| `embedding` | `_question_vectors` em [Search.md](Search.md) | pergunta | JSON com o denso (lista) e o esparso (índices + valores) |
| `answer` | `answer_question` em [Answer.md](Answer.md) | pergunta + filtros + limite + rerank + modelo + versão do prompt + MCP (URL e formula set) | `AnswerResult` serializado |

O embedding da pergunta é determinístico por modelo, então a chave é só o texto. A resposta depende de tudo o que muda o resultado: filtros, limite, rerank ligado, `llm_model`, `ANSWER_PROMPT_VERSION` e, se `MCP_HTTP_URL` estiver definida, a URL mais `MCP_FORMULA_SET_VERSION` (em `mcp_answer.py`) entram na chave.

## Falha e desligamento

`redis.RedisError` em get ou set chama `_mark_unavailable`: emite `cache.unavailable` em nível warning **uma vez por processo** e desliga o cache dali em diante — sem repetir o warning e sem pagar o timeout de conexão a cada consulta. A operação segue pelo caminho normal. Diferente do reranker, aqui o fallback é o comportamento esperado, não uma falha.

`CACHE_ENABLED=false` desliga pela configuração; `--no-cache` desliga por invocação (nem consulta o Redis).

## TTL e invalidação

TTL único, `CACHE_TTL_S` (padrão 24 h), aplicado no `SETEX`. Não há invalidação ativa: se um PDF for reingerido com conteúdo novo, respostas cacheadas ficam velhas até o TTL vencer. Essa janela é o preço aceito do cache de resposta.

## Eventos

| Evento | Quando |
|---|---|
| `cache.lookup` | Toda leitura, com `cache_scope` e `cache_hit` |
| `cache.unavailable` | Primeira falha de conexão do processo, nível warning |

`cache_set` não emite evento: a gravação é efeito colateral da operação, que já tem o seu. Resposta vinda do cache não emite `retrieve.*` nem `generate.*` — o `cache.lookup` com hit é o único evento dessa execução. Detalhes em [Tracing.md](Tracing.md), seção "Operação de cache".
