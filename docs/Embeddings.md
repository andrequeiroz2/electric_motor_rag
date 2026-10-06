# Embeddings

Referência de `src/eletric_motor/rag/embeddings.py`. Carrega os dois modelos locais de embedding e define os prefixos que cada um exige. Não emite evento de trace: quem registra é o chamador ([Store.md](Store.md), [Search.md](Search.md)).

Este arquivo é a descrição do comportamento implementado. Mudou o código, atualize este documento no mesmo passo.

## Bibliotecas

| Peça | Origem | Função neste módulo |
|---|---|---|
| `TextEmbedding` | `fastembed` | Modelo denso, via onnxruntime |
| `SparseTextEmbedding` | `fastembed` | Modelo esparso BM25 |
| `functools.cache` | biblioteca padrão | Uma instância de cada modelo por processo |

## Modelos

| Vetor | Modelo | Uso |
|---|---|---|
| `dense` | `intfloat/multilingual-e5-large` | 1024 dimensões, cosseno |
| `sparse` | `Qdrant/bm25` | Casamento lexical com IDF |

Trocar o modelo denso exige outra coleção: vetor gravado com 1024 dimensões não aceita outro tamanho (ver [Collection.md](Collection.md)).

## Prefixos do e5

O e5 foi treinado com prefixo de tarefa: documentos entram com `passage: `, consultas com `query: `. As constantes `PASSAGE_PREFIX` e `QUERY_PREFIX` existem para o chamador não escrever a string na mão. O esparso é lexical e recebe o texto cru, sem prefixo — nos dois lados (gravação e busca).

## Arena desligada

Os dois loaders passam `enable_cpu_mem_arena=False`. A arena do onnxruntime reserva blocos por formato de entrada e não devolve ao SO: 535 chunks de tamanhos variados levaram o processo a 27 GB e o kernel o matou. Com a arena desligada o RSS fica estável em ~9 GB. A saga está em `tasks/003_ingestao.md`.

## Threads

`EMBEDDING_THREADS` limita os núcleos do onnxruntime. Vazio, o runtime usa todos — o embedding compete por CPU com a busca e com o reranker. O mesmo limite vale para o reranker (ver [Rerank.md](Rerank.md)).

## Cache

`@cache` segura a instância: o modelo é baixado e carregado uma vez por processo, na primeira chamada. Quem chama `dense_model()` dez vezes recebe o mesmo objeto.
