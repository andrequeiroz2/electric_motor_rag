# Tracing

Referência de `src/eletric_motor/rag/trace.py`. Um evento de trace é uma linha JSON em stderr. O mesmo `trace_id` atravessa a entrada, a transformação e o erro de uma operação.

A frase da CLI continua em stdout. Este arquivo é a descrição do comportamento implementado. Mudou o código, atualize este documento no mesmo passo.

## Bibliotecas

Não há biblioteca de tracing. OpenTelemetry, structlog e logging de terceiros não entram até uma fase pedir.

| Peça | Origem | Função neste módulo |
|---|---|---|
| `logging` | biblioteca padrão | Entrega a linha ao handler |
| `logging.Formatter` | biblioteca padrão | `JsonFormatter` escreve a linha JSON |
| `logging.StreamHandler(sys.stderr)` | biblioteca padrão | Destino do trace |
| `contextvars.ContextVar` | biblioteca padrão | Guarda o `trace_id` da tarefa atual |
| `contextlib.contextmanager` | biblioteca padrão | Implementa `trace_scope` |
| `uuid` | biblioteca padrão | Gera `trace_id` com `uuid4().hex` (32 hex, sem hífen) |
| `json` | biblioteca padrão | Serializa o evento com `ensure_ascii=False` |
| `traceback` | biblioteca padrão | Acha o frame do projeto em `error_origin` |
| `time.perf_counter` | biblioteca padrão | Base de `elapsed_ms` |
| `datetime`, `timezone` | biblioteca padrão | Campo `ts` em UTC |
| `pathlib.Path` | biblioteca padrão | Caminho relativo do frame de erro |
| `pydantic.BaseModel` | `pydantic` v2 | `TraceContext` e `LogEvent`, modelos congelados |
| `ResponseHandlingException` | `qdrant_client` | Mensagem curta quando o Qdrant não responde |

`qdrant_client` aparece só em `error_message`. O módulo de trace não abre conexão e não conhece coleção, vetor ou documento.

## Arquitetura

```text
operação (init_collection, ingest_document, search_chunks ou answer_question)
  trace_scope / bind_trace     guarda trace_id na ContextVar
  log_event                    valida LogEvent e entrega ao logging
  logger eletric_motor         nível INFO, propagate False
  StreamHandler stderr
  JsonFormatter                imprime a linha já montada
```

Há um identificador por operação, não um span tree. Funções chamadas dentro da operação leem o mesmo `trace_id`. Outra thread ou outra task asyncio não vê esse valor: `ContextVar` é isolada por contexto.

Stdout e stderr são canais diferentes. `eletric-motor init-collection` imprime a frase humana em stdout. O JSON sai em stderr.

## Modelos

`TraceContext` é o miolo opcional do evento. `extra="forbid"`: campo desconhecido falha na validação. Todos os campos são opcionais. `None` some da linha JSON.

`LogEvent` herda `TraceContext` e acrescenta os cinco campos obrigatórios:

| Campo | Regra |
|---|---|
| `ts` | UTC, formato `YYYY-MM-DDTHH:MM:SSZ`, sem fração de segundo |
| `level` | `debug`, `info`, `warning` ou `error` |
| `event` | Nome estável. Não muda quando a mensagem muda |
| `trace_id` | String não vazia |
| `logger` | Nome do logger, em geral o `__name__` de quem emite |

A ordem gravada é fixa: `ts`, `level`, `event`, `trace_id`, `logger`, depois os campos de contexto que não são `None`.

Campos de contexto definidos hoje:

| Campo | Uso |
|---|---|
| `collection` | Nome da coleção |
| `created` | `true` se a coleção foi criada nesta chamada |
| `indexes_added` | Nomes dos índices de payload criados nesta chamada. Lista vazia é gravada |
| `dense_size` | Dimensão do vetor denso |
| `dense_vector_name` | Nome do vetor denso |
| `sparse_vector_name` | Nome do vetor esparso |
| `document_id` | Identificador do documento ingerido |
| `pages` | Páginas extraídas do PDF, `>= 1` |
| `sections` | Seções reconhecidas no documento |
| `chunks` | Chunks gerados do documento |
| `points_written` | Pontos novos gravados na coleção |
| `points_existing` | Pontos que já existiam na coleção |
| `points_updated` | Pontos existentes com payload atualizado, sem reembedar |
| `span` | Etapa da operação: `ingest`, `retrieve`, `rerank` ou `generate` |
| `filters` | Filtros de payload aplicados na consulta |
| `dense_hits` | Profundidade pedida ao braço denso |
| `sparse_hits` | Profundidade pedida ao braço esparso |
| `fused_hits` | Trechos devolvidos após a fusão RRF; no rerank, trechos após o corte do cross-encoder; na geração, trechos enviados ao LLM |
| `llm_model` | Nome do modelo de linguagem usado na geração |
| `answer_chars` | Tamanho da resposta gerada, em caracteres, `>= 0` |
| `rerank_model` | Nome do cross-encoder usado no rerank |
| `rerank_candidates` | Trechos fundidos enviados ao reranker, `>= 0` |
| `cache_scope` | O que o cache guarda: `embedding` ou `answer` |
| `cache_hit` | `true` se o valor estava no cache |
| `mcp_tool_count` | Chamadas MCP executadas no `answer` com `MCP_HTTP_URL`, `>= 0` |
| `mcp_tool_names` | Nomes das tools na ordem das chamadas (pode repetir) |
| `latency_ms` | Inteiro, milissegundos de `perf_counter` |
| `error_type` | `type(exc).__name__` |
| `error_message` | Primeira linha do erro, no máximo 200 caracteres |
| `error_file` | Caminho do frame do projeto, relativo ao pai do pacote |
| `error_line` | Número da linha, `>= 1` |
| `error_function` | Nome da função desse frame |

Campos de busca (`filters`, `dense_hits`, `sparse_hits`, `fused_hits`) e de resposta seguem a mesma regra: incluir um campo novo exige acrescentá-lo no modelo e neste documento.

## O que não entra na linha

- URL do Qdrant, usuário, senha ou connection string. `qdrant_url` não é campo de `TraceContext`.
- Corpo de documento, prompt, resposta do modelo ou texto integral de tabela.
- Stack trace. O traceback fica na exceção (`raise ... from exc`). O JSON leva só arquivo, linha e função do projeto.

`ResponseHandlingException` vira a mensagem fixa `Falha ao falar com o Qdrant`. Qualquer outro erro usa a primeira linha de `str(exc)`, cortada em 200 caracteres.

A frase da CLI pode mostrar a URL, porque é a orientação para quem está no terminal. Essa frase não é o evento JSON.

## Como uma linha é emitida

`log_event` exige um `trace_id` já definido. Sem ele, levanta `RuntimeError` com o texto `trace_id ausente`.

Passos:

1. Lê o `trace_id` da `ContextVar`.
2. Na primeira chamada do processo, `_configure` liga o logger `eletric_motor`: nível `INFO`, `propagate = False`, um `StreamHandler` em stderr com `JsonFormatter`. Chamadas seguintes não adicionam outro handler.
3. Monta um `LogEvent`. Campo de contexto com valor `None` é omitido.
4. Serializa com `model_dump(mode="json")` e `json.dumps(..., ensure_ascii=False)`. Tupla vira lista JSON.
5. Entrega ao logger filho (`eletric_motor.rag.collection`, por exemplo) com `extra={"trace_line": linha}`. O filho propaga até `eletric_motor`. O formatter vê `trace_line` e imprime essa string, sem prefixo `INFO:`.

O nome passado a `logger.log` é o próprio `event`. Quem lê o stderr vê só o JSON, porque o formatter ignora a mensagem padrão quando `trace_line` existe.

Nível `debug` não aparece com a configuração atual: o logger está em `INFO`.

## Escopo do trace_id

`trace_scope` sempre cria um id novo, guarda o token anterior e o restaura no `finally`. Use isto na borda da operação, como `init_collection`.

`bind_trace` cria um id só quando a `ContextVar` está vazia. Se já existe trace, devolve `None`. `release_trace(None)` não faz nada. `release_trace(token)` restaura o valor anterior. Use isto numa função pública que pode ser chamada sozinha ou por dentro de outra operação já rastreada.

`current_trace_id` só lê. Não cria id.

`elapsed_ms(started)` converte a diferença de `time.perf_counter()` para inteiro. Trunca a fração.

## Onde o erro aponta

`error_origin(exc)` percorre `traceback.extract_tb(exc.__traceback__)`. O pacote é o pai de `rag/`, a pasta `eletric_motor` que contém este módulo. O último frame cujo arquivo está dentro dessa pasta é o escolhido. Frame de `qdrant_client`, `httpx` ou outra dependência fica de fora.

O caminho gravado é relativo ao pai dessa pasta. No repositório isso produz `eletric_motor/rag/collection.py`, não um caminho absoluto da máquina.

Se nenhum frame cair no pacote, a função devolve `None` e os três campos de origem somem do JSON.

Isso aponta a linha deste projeto que disparou a falha. Com o Qdrant parado, a linha é a chamada `client.collection_exists(...)` em `_ensure_collection`. A linha diz onde a operação começou. Não afirma que essa linha está sintaticamente errada.

`error_origin` não segue `__cause__` nem `__context__`. Quem registra o erro precisa passar a exceção original, não o `SystemExit` criado depois para a CLI.

## Operação da coleção

`init_collection` abre `trace_scope` e emite `collection.init.started` com `collection`, `dense_size`, `dense_vector_name` e `sparse_vector_name`.

Em seguida chama `ensure_collection`. Como o trace já existe, `bind_trace` devolve `None`: essa função não emite outra entrada e não emite o erro. Quem emite o erro é `init_collection`.

Sucesso: `_ensure_collection` emite `collection.ensured` com `collection`, `created`, `indexes_added` e `latency_ms`. Esse relógio começa no início de `ensure_collection`, depois da leitura de `Settings`.

Falha de conexão: `init_collection` captura `ResponseHandlingException`, emite `collection.init.failed` e levanta `SystemExit` com a frase para subir o Docker. O `from exc` preserva a causa fora do JSON.

Falha de coleção incompatível: `_require_compatible` levanta `SystemExit`. `ensure_collection` não registra, porque não abriu o trace. `init_collection` captura esse `SystemExit`, emite `collection.init.failed` e relança.

`ensure_collection` chamada sem trace aberto faz o trio completo: `bind_trace` cria o id, emite `collection.init.started`, emite `collection.ensured` ou `collection.init.failed`, e `release_trace` limpa o id. O erro registrado nesse caminho é `ResponseHandlingException` ou `SystemExit`.

O relógio de `collection.init.failed` dentro de `init_collection` começa antes do `QdrantClient`. O de `collection.ensured` começa dentro de `ensure_collection`. Os dois números medem trechos diferentes.

## Eventos

Nome é contrato.

| Evento | Quando |
|---|---|
| `collection.init.started` | Entrada da configuração da coleção |
| `collection.ensured` | Coleção criada ou conferida, índices aplicados |
| `collection.init.failed` | A mesma operação falhou |
| `ingest.document.started` | Entrada da ingestão de um PDF |
| `ingest.document.extracted` | PDF extraído pelo Docling, com páginas e seções |
| `ingest.document.chunked` | Documento cortado em chunks, com contagens |
| `ingest.document.stored` | Chunks gravados na coleção, com contagens de pontos |
| `ingest.document.completed` | PDF extraído, cortado e gravado |
| `ingest.document.failed` | A ingestão do documento falhou |
| `retrieve.hybrid.completed` | Consulta híbrida fundida, com contagens e latência |
| `retrieve.hybrid.failed` | A consulta híbrida falhou |
| `rerank.completed` | Trechos reordenados pelo cross-encoder, com contagens e latência |
| `rerank.failed` | O rerank falhou |
| `generate.answered` | Resposta do LLM gerada, com modelo e tamanho |
| `generate.mcp.tools_called` | Após fluxo MCP no `answer`: contagem e nomes das tools invocadas |
| `generate.failed` | A chamada ao LLM falhou |
| `cache.lookup` | Consulta ao cache, com `cache_scope` e `cache_hit` |
| `cache.unavailable` | Redis inalcançável; warning, uma vez por processo |

Exemplo real de sucesso, stderr:

```json
{"ts": "2026-10-02T12:49:06Z", "level": "info", "event": "collection.init.started", "trace_id": "d293c433bc1c433dbd045b4a927a4103", "logger": "eletric_motor.rag.collection", "collection": "eletric_motor", "dense_size": 1024, "dense_vector_name": "dense", "sparse_vector_name": "sparse"}
{"ts": "2026-10-02T12:49:06Z", "level": "info", "event": "collection.ensured", "trace_id": "d293c433bc1c433dbd045b4a927a4103", "logger": "eletric_motor.rag.collection", "collection": "eletric_motor", "created": false, "indexes_added": [], "latency_ms": 10}
```

Exemplo real de Qdrant parado:

```json
{"ts": "2026-10-02T12:55:57Z", "level": "error", "event": "collection.init.failed", "trace_id": "e666c2e97a184c6a9e5a2e9836c7780f", "logger": "eletric_motor.rag.collection", "collection": "eletric_motor", "latency_ms": 31, "error_type": "ResponseHandlingException", "error_message": "Falha ao falar com o Qdrant", "error_file": "eletric_motor/rag/collection.py", "error_line": 49, "error_function": "_ensure_collection"}
```

Os dois eventos de uma execução compartilham `trace_id`. Entrada e erro, ou entrada e transformação, são o par esperado. `collection.ensured` e `collection.init.failed` não saem juntos na mesma operação.

## Operação de resposta

`answer_question` abre o trace com `bind_trace` e chama `search_chunks`. A busca não abre outro trace: `retrieve.hybrid.completed` e o evento da geração saem com o mesmo `trace_id`.

Sem `OPENAI_API_KEY`, a operação para antes de qualquer evento: nenhum `generate.*` sai no stderr e a frase da CLI orienta a configurar a chave.

Sucesso: com `MCP_HTTP_URL`, `generate.mcp.tools_called` (em `mcp_answer`) precede `generate.answered` no mesmo `trace_id`, com `mcp_tool_count`, `mcp_tool_names` e `latency_ms` só da fase MCP+LLM com tools.

Sucesso: `generate.answered` com `span="generate"`, `collection`, `filters`, `fused_hits` (trechos enviados ao LLM), `llm_model`, `answer_chars` e `latency_ms`. O relógio começa na entrada de `answer_question`, antes da busca.

Falha na chamada ao LLM: `generate.failed` com `error_type`, `error_message` e a origem no projeto. Falha na busca (Qdrant parado) sobe como `SystemExit` de `search_chunks`: quem registra é o `retrieve.hybrid.failed`, e a geração não emite evento.

A chave da API não é campo de `TraceContext`. O prompt e a resposta não entram na linha: o tamanho da resposta vai em `answer_chars`.

## Operação de rerank

Com `rerank` ligado, `search_chunks` pede `rerank_candidates` trechos à fusão RRF e os reordena com o cross-encoder antes de cortar no `limit`. O evento sai no mesmo `trace_id` do retrieve, entre `retrieve.hybrid.completed` e a resposta da função.

Sucesso: `rerank.completed` com `span="rerank"`, `collection`, `rerank_model`, `rerank_candidates`, `fused_hits` (trechos devolvidos após o corte) e `latency_ms`. O relógio cobre só o cross-encoder, não a busca.

Falha: `rerank.failed` com os campos de erro de sempre, e a operação sobe como `SystemExit`. Não há fallback silencioso para a ordem RRF. O `retrieve.hybrid.completed` já foi emitido nesse caminho: o `except SystemExit` de `search_chunks` não repete o `retrieve.hybrid.failed`.

## Operação de cache

`cache_get` emite `cache.lookup` com `span="cache"`, `cache_scope` (`embedding` ou `answer`), `cache_hit` e `latency_ms`. `cache_set` não emite evento: a gravação é efeito colateral da operação que já tem o seu evento.

Resposta vinda do cache não emite `retrieve.*` nem `generate.*`: o único evento dessa execução é o `cache.lookup` com hit. Emitir `generate.answered` sem chamada ao LLM seria mentira no trace.

Redis inalcançável emite `cache.unavailable` em nível warning, com os campos de erro de sempre, e desliga o cache pelo resto do processo: a operação segue sem cache e o warning não se repete. Cache é otimização, não infraestrutura crítica — diferente do reranker, aqui o fallback é o caminho normal.

A chave de cache (SHA-256 dos dados que definem o resultado) e o valor cacheado não entram na linha.

## Como emitir um evento novo

1. Abrir `trace_scope` na borda da operação. Se a função também puder ser chamada por dentro de outra já rastreada, usar `bind_trace` e `release_trace`.
2. Emitir a entrada com `log_event` e um `TraceContext` só com dados não sigilosos.
3. Emitir a transformação no ponto em que o resultado existe, com `latency_ms=elapsed_ms(started)`.
4. No `except`, emitir o evento de falha com `level="error"`, `error_type`, `error_message(exc)` e, se a origem existir, `error_origin(exc)`. Relançar a exceção depois do log.
5. Registrar o nome do evento na tabela deste documento antes de usar o nome no código.
6. Se o dado não cabe num campo já existente, acrescentar o campo em `TraceContext` e na tabela de campos. Não enfiar dict solto: `extra="forbid"`.

```python
from time import perf_counter

from eletric_motor.rag.trace import TraceContext, elapsed_ms, log_event, trace_scope

def run() -> None:
    with trace_scope():
        started = perf_counter()
        log_event(
            "retrieve.hybrid.completed",
            logger_name=__name__,
            context=TraceContext(collection="eletric_motor", latency_ms=elapsed_ms(started)),
        )
```

O exemplo usa só campos já declarados. Para um dado novo, estenda o modelo primeiro: campo desconhecido falha na validação por causa do `extra="forbid"`.
