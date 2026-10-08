# Answer

Referência de `src/eletric_motor/rag/answer.py` e, com MCP, `mcp_answer.py`. Responde a pergunta com o LLM usando os trechos recuperados, em prosa contínua em português. Com `MCP_HTTP_URL`, números determinísticos vêm das tools HTTP ([MCP.md](MCP.md)). A busca é [Search.md](Search.md).

Este arquivo é a descrição do comportamento implementado. Mudou o código, atualize este documento no mesmo passo.

## Bibliotecas

| Peça | Origem | Função neste módulo |
|---|---|---|
| `ChatOpenAI` | `langchain-openai` | Chamada ao modelo, temperatura 0 |
| `SystemMessage`, `HumanMessage` | `langchain-core` | As duas mensagens do prompt |
| `re` | biblioteca padrão | Extrai `[n]` legados na resposta (auditoria opcional) |
| `search_chunks` | [Search.md](Search.md) | Os trechos que viram contexto |
| `Client` | `mcp` | Cliente Streamable HTTP (só em `mcp_answer.py`) |
| `ToolMessage`, tool calling | `langchain-core` / `langchain-openai` | Loop LLM ↔ MCP quando URL configurada |

## Arquitetura

```text
answer_question              bind_trace, chave conferida antes de tudo
  cache Redis                hit devolve o AnswerResult e encerra
  search_chunks              busca híbrida (+ rerank por padrão)
  _generate ou generate_with_mcp   se `MCP_HTTP_URL` estiver definida, LLM + tools HTTP
  _generate                  senão: prompt de sistema + trechos -> LLM (só texto)
  cache_set                  grava o resultado com o TTL de Settings
  AnswerResult.hits          trechos enviados ao prompt (ordem de relevância)
```

A chave do cache leva pergunta, filtros, limite, rerank, `llm_model`, `ANSWER_PROMPT_VERSION` e, com MCP, `MCP_HTTP_URL` + versão do conjunto de fórmulas — tudo o que muda o resultado (ver [Cache.md](Cache.md)). Resposta vinda do cache não emite `retrieve.*` nem `generate.*`: o `cache.lookup` com hit é o único evento da execução.

## O prompt

O sistema manda: prosa contínua para terminal; primeiro parágrafo com resposta direta; parágrafos seguintes com definições e detalhes dos trechos, integrados naturalmente; sem `[n]`, sem listar fontes e sem colar `###` do Markdown; só conhecimento dos trechos; síntese quando o valor exato falta; recusa quando nenhum trecho se relaciona à pergunta.

Com MCP, um complemento ao system prompt manda usar as tools para corrente, rendimento, Ip/In e validação de queda antes de concluir, integrando o resultado na prosa com unidades.

Os trechos numerados `[1]`, `[2]`… continuam na mensagem humana (título, seção, página, conteúdo) como referência interna para o modelo — a instrução explicita não citar `[n]` na resposta final.

`ANSWER_PROMPT_VERSION` (hoje `3`) incrementa quando o contrato de saída muda, para invalidar entradas antigas no cache Redis. Com MCP, a chave inclui também `MCP_HTTP_URL` e a versão do conjunto de fórmulas.

## Orçamento de tokens

Chunk de tabela é a tabela inteira, sem limite de tamanho: 16 trechos com grades grandes pediram 50 mil tokens à API e tomaram 429 (a cota TPM da organização era 30 mil — nem retry resolveria). `_fit_budget` corta esse risco em dois níveis, medidos em `cl100k_base`:

1. Trecho acima de 2000 tokens é truncado com o marcador `[... trecho truncado ...]`.
2. Os trechos entram no prompt por ordem de relevância até o teto `llm_context_tokens` (padrão 12000); o primeiro que não cabe encerra a lista.

`AnswerResult.hits` guarda só os trechos que foram ao prompt. No trace, o `fused_hits` do `generate.answered` é a contagem enviada: `retrieve` fundiu 24, `rerank` cortou em 16, o orçamento pode cortar mais.

A disciplina é comportamental: a busca devolve os trechos mais próximos mesmo fora do domínio; o prompt impede inventar (ex.: personagens de ficção). A CLI com `--sources` lista os trechos do prompt para auditoria humana.

## Modelo

`AnswerResult`: `answer`, `hits` (trechos enviados) e `llm_model`. A propriedade `cited_hits` extrai `[n]` do texto, se existirem — no fluxo normal de prosa fica vazia. Serve para respostas legadas ou se o modelo desobedecer e usar marcadores.

## Saída na CLI

Por padrão imprime só `answer`. Com `--sources`, após a resposta lista `Trechos usados no prompt:` na ordem de `hits`, com título, caminho da seção e snippet (500 caracteres, corte em fim de frase).

## Chave e falhas

Sem `OPENAI_API_KEY`, a operação para antes de qualquer evento ou chamada de rede, com a frase orientando a configurar. Falha na busca sobe como o `SystemExit` de `search_chunks` (quem registra é o retrieve). Com `MCP_HTTP_URL` e servidor MCP indisponível, `generate_with_mcp` encerra com `SystemExit` explícito (não degrada para só RAG). Falha na chamada ao LLM emite `generate.failed` e vira `SystemExit` "Não consegui gerar a resposta." — a causa original fica no `from exc`.

## Eventos

| Evento | Quando |
|---|---|
| `generate.mcp.tools_called` | Fluxo MCP concluiu; em `mcp_answer.py`, com `mcp_tool_count`, `mcp_tool_names` e `latency_ms` só da fase MCP+LLM |
| `generate.answered` | Resposta gerada, com `llm_model`, `answer_chars`, `fused_hits` (trechos enviados) e `latency_ms` medido desde a entrada, antes da busca |
| `generate.failed` | A chamada ao LLM falhou |

Prompt e resposta nunca entram no JSON: o tamanho da resposta vai em `answer_chars`. A chave não é campo de trace. Detalhes em [Tracing.md](Tracing.md), seção "Operação de resposta".
