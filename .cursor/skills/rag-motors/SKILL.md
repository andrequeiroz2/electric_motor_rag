---
name: rag-motors
description: >-
  Aplica a arquitetura RAG de motores elétricos deste repositório: LangChain,
  Qdrant híbrido, chunking técnico e fases pequenas. Use ao implementar,
  alterar ou revisar ingestão, embeddings, busca, citação, Qdrant, Docling,
  BM25 ou o pipeline RAG.
---

# RAG de motores elétricos

Implemente só a fase que o usuário pediu. Não antecipe Redis, reranker nem MCP.

## Fases

1. Coleção `motores` no Qdrant — feita.
2. Ingestão de um PDF: Docling, chunk, dois vetores.
3. Consulta híbrida com filtro de metadado.
4. Resposta do LLM com citação de fonte, seção e trecho do texto. Página não aparece: o usuário não tem o PDF.
5. Redis: cache de embedding e de resposta.
6. Reranker `jinaai/jina-reranker-v2-base-multilingual` via fastembed (o `bge-reranker-v2-m3` do plano original não é suportado pelo fastembed; usá-lo puxaria PyTorch).
7. MCP: `calcular_corrente_nominal` e `calcular_queda_tensao`.

## Stack fixa

- Python 3.13, `uv`, pacote `eletric_motor`.
- Orquestração: `langchain`, `langchain-core`, `langchain-text-splitters`, `langchain-qdrant`.
- Banco: Qdrant local via `compose.yaml`. Cliente `qdrant-client`.
- Embeddings locais: `fastembed`. Denso `intfloat/multilingual-e5-large` (1024, cosseno). Esparso `Qdrant/bm25`.
- PDF: `docling`, saída Markdown.
- Dependência nova só quando a fase em curso precisar dela.

Não troque o banco por Chroma ou Pinecone. Não use `all-MiniLM-L6-v2`. Não indexe TF-IDF à parte: o BM25 esparso cobre o casamento lexical.

## Coleção

Nome padrão `motores`. Vetor `dense` cosseno 1024. Vetor `sparse` com modificador IDF. Criação idempotente em `eletric_motor.rag.collection`. Se a coleção existir com tamanho ou distância diferentes, pare: trocar o modelo exige outra coleção.

Índices de payload: `source_type`, `manufacturer`, `topic`, `norm_code`, `language`.

## Chunk

Docling gera Markdown. O primeiro corte segue títulos. Prosa acima do limite passa pelo splitter recursivo, em tokens.

- Prosa: 500–800 tokens, sobreposição 80–120.
- Tabela: um chunk inteiro, com o título da seção no início. Sem sobreposição.
- Cada ponto guarda `section_path`, `page`, `document_title`, `content_hash`.

## Metadados

| Campo | Valores |
|---|---|
| `source_type` | `manual`, `norma`, `guia` |
| `manufacturer` | `weg`, `schneider`, `siemens`, `abnt` |
| `topic` | `fundamentos`, `dimensionamento`, `calculos`, `instalacao`, `partida`, `normas` |
| `norm_code` | ex. `5410` |
| `language` | `pt-BR` |

A taxonomia técnica é filtro, não árvore de pastas. Norma ABNT só entra com cópia obtida legalmente. Sem licença, indexe a referência do item, sem o texto integral.

## Consulta

Padrão: `RetrievalMode.HYBRID`, prefetch 40 densos e 40 esparsos, fusão RRF, 8 trechos (16 na resposta do LLM). Filtro de payload quando a pergunta cita norma, fabricante ou tópico. Se o modelo denso falhar, a mesma coleção responde em modo esparso. A resposta cita fonte e seção, e lista só os trechos citados, com o texto de cada um.
