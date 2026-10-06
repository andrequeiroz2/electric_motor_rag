# Ingest

Referência de `src/eletric_motor/rag/ingest.py`. Extrai um PDF com o Docling e monta o documento em seções com hierarquia e página. É a primeira das três etapas da ingestão: extrair ([Ingest.md](Ingest.md)), cortar ([Chunk.md](Chunk.md)), gravar ([Store.md](Store.md)).

Este arquivo é a descrição do comportamento implementado. Mudou o código, atualize este documento no mesmo passo.

## Bibliotecas

| Peça | Origem | Função neste módulo |
|---|---|---|
| `DocumentConverter` | `docling` | Converte o PDF em documento navegável |
| `PdfPipelineOptions`, `TableFormerMode` | `docling` | Fixa a extração de tabelas no modo `FAST` |
| `InputFormat`, `PdfFormatOption` | `docling` | Liga as opções ao formato PDF |
| `pydantic.BaseModel` | `pydantic` v2 | `DocumentSection`, `ExtractedDocument`, `IngestResult`, modelos congelados |
| `re` | biblioteca padrão | Numeração de seção e limpeza de caracteres de controle |
| `trace_scope`, `bind_trace` | `eletric_motor.rag.trace` | Borda e meio da operação rastreada |

## Arquitetura

```text
ingest_document          borda: trace_scope, orquestra as três etapas
  extract_document       PDF -> ExtractedDocument (bind_trace: usável sozinha)
    _extract             varre os itens do Docling e monta as seções
  chunk_document         ExtractedDocument -> chunks        (Chunk.md)
  store_chunks           chunks -> pontos no Qdrant         (Store.md)
```

`ingest_document` é o caminho completo do comando `eletric-motor ingest`. `extract_document` é pública porque a extração sozinha já é útil para inspecionar um PDF.

## Modelos

`DocumentSection`: `section_path` (tupla da hierarquia, ex. `("6 INSTALAÇÃO", "6.9 CONEXÃO ELÉTRICA")`), `page` da página onde a seção começa e `markdown` com o conteúdo.

`ExtractedDocument`: `document_id` (nome do arquivo sem `.pdf`), `document_title` (título da primeira seção), `pages` e a tupla de seções.

`IngestResult`: o documento, os chunks e o `StoreResult` — a saída completa da ingestão.

## TableFormer em modo FAST

O modo `accurate`, default do Docling, mutilou grades grandes: a Tabela 1.2 do guia teve 924 de 926 células descartadas e sobrou uma grade 2×2. O modo `FAST` extraiu a mesma tabela como 46×31. O pipeline fixa `TableFormerMode.FAST` em `_converter`. A história completa está em `tasks/003_ingestao.md`.

## Como vira seção

O Docling não informa o nível de um título; a hierarquia vem da numeração no texto. `_SECTION_NUMBER` reconhece `1 T`, `1. T`, `1.2 T` e `16.Dados Elétricos` (numeração colada, usada no catálogo W22). A profundidade é o número de pontos mais um, limitada a `_MAX_SECTION_DEPTH = 4`. Caracteres de controle no título viram espaço antes de tudo.

A varredura mantém uma pilha de títulos: a cada `section_header`, o buffer atual vira uma `DocumentSection` com o caminho da pilha, a pilha é podada no nível do título novo e o título entra nela. O Markdown da seção começa com o título prefixado em `#` na profundidade certa.

Itens com rótulo `picture`, `document_index` ou `footnote` são descartados. `list_item` sem marcador ganha `- ` na frente. Tabela vira Markdown pela exportação do próprio Docling.

## Ruído de página

Nem todo `section_header` é seção. Três filtros por documento, todos em `casefold`:

| Filtro | O que é | Exemplo |
|---|---|---|
| `_PAGE_HEADERS` | Cabeçalho repetido no alto das páginas | "Acessórios Opcionais" no guia |
| `_TOP_LEVELS` | Títulos sem numeração que abrem capa e índice | "Linha W22", "Índice" |
| `_FALSE_HEADERS` | Caixas numeradas que não são seção | "8. Recomendações adicionais:" no manual |

A caixa "8. Recomendações adicionais:" é referência cruzada do manual; sem o filtro, ela roubava a hierarquia das seções 6.x. Um título que não é ruído conhecido e não tem numeração nem prefixo de nível superior é descartado.

## Falhas

Arquivo inexistente levanta `FileNotFoundError`. PDF sem página ou sem trecho de texto levanta `ValueError`. Qualquer falha vira `SystemExit` com frase em português e evento `ingest.document.failed`; a causa original fica no `from exc`.

## Eventos

| Evento | Quando |
|---|---|
| `ingest.document.started` | Entrada da ingestão ou da extração isolada |
| `ingest.document.extracted` | PDF extraído, com `pages` e `sections` |
| `ingest.document.completed` | As três etapas concluídas, com todas as contagens |
| `ingest.document.failed` | Qualquer etapa falhou |

No caminho completo, `extract_document`, `chunk_document` e `store_chunks` acham o trace já aberto e não repetem a entrada nem o erro: quem registra a falha é `ingest_document`, com `exc.__cause__` quando existe.
