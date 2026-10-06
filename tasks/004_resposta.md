# 004 — Resposta do LLM com citação

Task de implementação. Responde em português uma pergunta em linguagem natural usando os trechos da coleção `eletric_motor`, com citação de fonte, seção e página. Esta task não usa Redis, reranker nem MCP.

A busca híbrida já existe em `search.py` e devolve os trechos com `section_path`, `page` e `document_title`. Esta task não muda a coleção, não reingere PDF e não cria índice novo.

Cada fase nasce pendente. Ao terminar a implementação e a verificação descritas nela, o status nesta tabela passa a `concluída`. Código escrito sem essa verificação permanece `pendente`. A fase seguinte só começa com a anterior `concluída`.

| Fase | Entrega | Status |
|---|---|---|
| 1 | Módulo `answer.py` com prompt e chamada ao LLM | concluída |
| 2 | Comando `answer` na CLI | concluída |
| 3 | Trace `generate.answered` / `generate.failed` | concluída |

O comando é `eletric-motor answer PERGUNTA`, com as mesmas flags de filtro do `query`. O limite padrão é 16 trechos (o dobro do `query`: com 8, trechos-chave como a placa de identificação ficavam fora e a resposta vinha vazia). Dado que cruza função é modelo Pydantic v2 congelado. O JSON de trace não leva prompt, resposta do modelo nem texto integral de trecho.

## Regras comuns às fases

- LLM: OpenAI via `langchain-openai`, modelo default `gpt-4o`, temperatura 0. A chave vem de `OPENAI_API_KEY` (ambiente ou `.env`, que o Git não versiona). Sem chave, o comando para com frase em português antes de chamar a rede.
- O prompt manda responder só com base nos trechos numerados e citar `[n]` ao final de cada afirmação. Se os trechos não bastam, o modelo diz que não encontrou resposta na documentação.
- Cada trecho numerado mostra `document_title`, `section_path` e `page`. A resposta impressa lista só as fontes citadas no texto, com título, caminho da seção e o trecho do texto. Página não aparece na saída: o usuário não tem o PDF.
- Eventos no mesmo `trace_id` da busca: `retrieve.hybrid.completed` primeiro, `generate.answered` ou `generate.failed` depois.

## Fase 1 — Módulo de resposta

Entrada: pergunta, filtros e limite, como no `query`.

`answer_question` chama `search_chunks`, monta o prompt com os trechos numerados e chama o LLM. Saída: `AnswerResult` com o texto da resposta e os trechos usados.

Verificação: sem `OPENAI_API_KEY`, a chamada para com a frase de orientação e nenhum evento `generate.*` sai no stderr. Com chave, a resposta cita `[n]` e cada `n` existe na lista de trechos.

## Fase 2 — Comando na CLI

`eletric-motor answer "pergunta"` imprime a resposta e, em seguida, a lista `Fontes citadas:` com título, caminho da seção e o trecho do texto de cada fonte citada. Ajuda em português.

Verificação: a pergunta de regressão "como dimensionar condutores para motor trifásico" responde com base no §6.9 do manual e cita a fonte com página.

## Fase 3 — Trace da geração

`generate.answered` leva `span="generate"`, `collection`, `filters`, `fused_hits`, `llm_model`, `answer_chars` e `latency_ms`. `generate.failed` leva `error_type`, `error_message` e a origem do erro no projeto. Os campos novos entram em `TraceContext` e em `docs/Tracing.md` no mesmo passo.

Verificação: uma execução com sucesso emite `retrieve.hybrid.completed` e `generate.answered` com o mesmo `trace_id`. Uma falha forçada (modelo inexistente) emite `generate.failed` com `error_file` dentro de `eletric_motor`.

## Critério de pronto desta task

As três linhas da tabela de fases estão `concluída`. A resposta cita fonte, seção e página. Nenhuma chave foi commitada no Git.
