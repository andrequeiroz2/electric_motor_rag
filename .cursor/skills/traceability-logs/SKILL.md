---
name: traceability-logs
description: >-
  Define o formato de log estruturado deste projeto para rastrear entrada,
  transformação e erro. Use ao criar, alterar ou revisar logging, tracing,
  eventos, erros operacionais ou correlação de uma consulta.
---

# Logs de rastreabilidade

A referência canônica é [docs/Tracing.md](../../../docs/Tracing.md). Um evento é uma linha JSON em stderr. O mesmo `trace_id` atravessa a entrada, a transformação e o erro. A mensagem da CLI continua em stdout. A URL do Qdrant não entra no log.

Use `trace_scope` e `log_event` em `eletric_motor.rag.trace`, com o `logging` da biblioteca padrão e um formatter JSON. Não adicione biblioteca de log até uma fase pedir.

## Campos obrigatórios

| Campo | Conteúdo |
|---|---|
| `ts` | ISO-8601 em UTC |
| `level` | `debug`, `info`, `warning`, `error` |
| `event` | nome estável em `snake.case` com domínio |
| `trace_id` | identificador da operação |
| `logger` | módulo, ex. `eletric_motor.rag.collection` |

## Campos quando existirem

`span` (`ingest`, `retrieve`, `generate`), `collection`, `created`, `indexes_added`, `dense_size`, `dense_vector_name`, `sparse_vector_name`, `document_id`, `content_hash`, `page`, `section_path`, `filters`, `dense_hits`, `sparse_hits`, `fused_hits`, `latency_ms`, `error_type`, `error_message`, `error_file`, `error_line`, `error_function`.

`error_file`, `error_line` e `error_function` são o último frame dentro do pacote `eletric_motor`. A stack continua fora do JSON. Detalhe em docs/Tracing.md.

`mcp_tool_count` e `mcp_tool_names` aparecem em `generate.mcp.tools_called`.

## O que não entra no log

- Chave de API, segredo ou connection string.
- Corpo integral do documento, do prompt ou da resposta.
- Texto completo da tabela indexada.

Pode entrar identificador, contagem, hash, filtro, latência e a mensagem curta do erro.

## Nomes de evento

O nome é contrato. Não o renomeie ao mudar a mensagem.

- `collection.init.started` — entrada da configuração, sem URL
- `collection.ensured` — transformação da coleção
- `collection.init.failed` — erro da mesma operação
- `ingest.document.started`
- `ingest.document.completed`
- `ingest.document.failed`
- `retrieve.hybrid.completed`
- `retrieve.hybrid.failed`
- `generate.answered`
- `generate.mcp.tools_called` — tools MCP no `answer` (`mcp_tool_count`, `mcp_tool_names`)
- `generate.failed`

## Exemplo

```json
{"ts":"2026-10-01T17:00:00Z","level":"info","event":"retrieve.hybrid.completed","trace_id":"8f3c","logger":"eletric_motor.rag.retrieve","span":"retrieve","collection":"motores","filters":{"norm_code":"5410"},"dense_hits":40,"sparse_hits":40,"fused_hits":8,"latency_ms":37}
```

Erro no mesmo `trace_id`, com `error_type` e `error_message`. Sem stack trace no campo de mensagem; a stack fica no handler de exceção, não no JSON de negócio.
