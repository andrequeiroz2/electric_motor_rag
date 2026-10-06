# Answer

Referência de `src/eletric_motor/rag/answer.py`. Responde a pergunta com o LLM usando só os trechos recuperados, com citação numerada das fontes. É a última milha do RAG: a busca é [Search.md](Search.md).

Este arquivo é a descrição do comportamento implementado. Mudou o código, atualize este documento no mesmo passo.

## Bibliotecas

| Peça | Origem | Função neste módulo |
|---|---|---|
| `ChatOpenAI` | `langchain-openai` | Chamada ao modelo, temperatura 0 |
| `SystemMessage`, `HumanMessage` | `langchain-core` | As duas mensagens do prompt |
| `re` | biblioteca padrão | Extrai os `[n]` da resposta |
| `search_chunks` | [Search.md](Search.md) | Os trechos que viram contexto |

## Arquitetura

```text
answer_question              bind_trace, chave conferida antes de tudo
  search_chunks              busca híbrida (+ rerank por padrão)
  _generate                  prompt de sistema + trechos numerados -> LLM
  AnswerResult.cited_hits    só as fontes citadas, na ordem da resposta
```

## O prompt

O sistema manda: responder em português; ser direto, com a resposta na primeira frase; basear cada afirmação nos trechos e citar `[n]` ao final da frase; não usar conhecimento de fora. Se o valor exato não estiver nos trechos, explicar o que a documentação oferece — como obter ou calcular — em vez de só dizer que falta. Só declarar "não cobre" quando nenhum trecho tiver relação.

A mensagem humana leva a pergunta e os trechos numerados, cada um com título do documento, caminho da seção, página e conteúdo.

A disciplina é comportamental, não mecânica: a busca sempre devolve os "mais próximos", mesmo para pergunta fora do domínio, e é o prompt que impede o modelo de responder "Bruce Wayne". A conferência das citações (`cited_hits`) é a auditoria dessa disciplina.

## Modelo

`AnswerResult`: `answer`, `hits` (todos os trechos enviados) e `llm_model`. A propriedade `cited_hits` extrai os `[n]` do texto e devolve só os hits citados, na ordem em que aparecem na resposta. Citação fora do intervalo é ignorada. É ela que alimenta a lista "Fontes citadas" da CLI — fonte não citada não aparece, e resposta sem citação nenhuma é sinalizada.

## Chave e falhas

Sem `OPENAI_API_KEY`, a operação para antes de qualquer evento ou chamada de rede, com a frase orientando a configurar. Falha na busca sobe como o `SystemExit` de `search_chunks` (quem registra é o retrieve). Falha na chamada ao LLM emite `generate.failed` e vira `SystemExit` "Não consegui gerar a resposta." — a causa original fica no `from exc`.

## Eventos

| Evento | Quando |
|---|---|
| `generate.answered` | Resposta gerada, com `llm_model`, `answer_chars`, `fused_hits` (trechos enviados) e `latency_ms` medido desde a entrada, antes da busca |
| `generate.failed` | A chamada ao LLM falhou |

Prompt e resposta nunca entram no JSON: o tamanho da resposta vai em `answer_chars`. A chave não é campo de trace. Detalhes em [Tracing.md](Tracing.md), seção "Operação de resposta".
