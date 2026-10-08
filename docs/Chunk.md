# Chunk

Referência de `src/eletric_motor/rag/chunk.py`. Corta o `ExtractedDocument` em chunks com metadados. Prosa acima do limite passa pelo splitter recursivo em tokens; tabela é um chunk inteiro com o título da seção no início.

Este arquivo é a descrição do comportamento implementado. Mudou o código, atualize este documento no mesmo passo.

## Bibliotecas

| Peça | Origem | Função neste módulo |
|---|---|---|
| `RecursiveCharacterTextSplitter` | `langchain-text-splitters` | Corta a prosa longa em tokens |
| `tiktoken` | `tiktoken` | Conta tokens no `cl100k_base`, tokenizador de referência do projeto |
| `detect`, `DetectorFactory` | `langdetect` | Idioma de cada seção do manual trilíngue |
| `hashlib` | biblioteca padrão | `content_hash` em SHA-256 |
| `pydantic.BaseModel` | `pydantic` v2 | `DocumentProfile` e `Chunk`, modelos congelados |

## Arquitetura

```text
chunk_document               bind_trace: usável sozinha ou dentro da ingestão
  _chunk                     perfil do documento + laço nas seções
    _language_of             idioma da seção (só no manual trilíngue)
    _section_chunks
      _split_blocks          separa prosa de tabela, costura legendas
      _split_prose           splitter recursivo se passar de 800 tokens
      _make_chunk            monta o Chunk com hash, tokens e metadados
```

## Modelos

`DocumentProfile` registra os metadados fixos de cada PDF admitido: `source_type` (`manual`, `norma` ou `guia`), `manufacturer`, `language`, `detect_language` e, para normas, `norm_code` opcional (ex.: `5410` na NBR 5410). O registro é o dicionário `_DOCUMENTS`, chaveado pelo `document_id`. **Documento fora dessa lista não é ingerido**: `_chunk` para com `SystemExit` orientando a registrar o perfil aqui. O `norm_code` do perfil é copiado para cada chunk e indexado no Qdrant.

`Chunk` é o que vira ponto no Qdrant: `document_id`, `document_title`, `section_path`, `page`, `kind` (`prose` ou `table`), `content`, `content_hash` (64 hex), `tokens`, `source_type`, `manufacturer`, `language`, `topic` e `norm_code`. O payload gravado é exatamente esse modelo, e a busca o valida de volta com `Chunk.model_validate`.

## Prosa e tabela

- Prosa: splitter recursivo com `chunk_size=800` e `chunk_overlap=100`, medidos em tokens `cl100k_base`. Bloco curto vira um chunk só, sem splitter.
- Tabela: um chunk inteiro, sem sobreposição, começando com o título da seção. A legenda exportada com a tabela entra no chunk; a repetição da legenda logo após a tabela é descartada.
- Bloco de "prosa" sem nenhuma palavra de 3+ letras fora do título (ex.: seção só com figura) é descartado.

## Idioma

`detect_language=True` (manual trilíngue): cada seção passa pelo langdetect com seed fixa (`DetectorFactory.seed = 0` — sem seed o veredito muda entre reingestões e o mesmo trecho viraria outro ponto). Amostra de 3000 caracteres; texto mais longo não muda o veredito e só atrasa. O mapa cobre `pt→pt-BR`, `en`, `es`; qualquer outro veredito ou falha cai no idioma da seção anterior — um trecho sem idioma reconhecido herda o contexto em vez de chutar.

## Tópico

`_topic_for` procura as palavras-chave no caminho da seção, em ordem de prioridade: `partida`, `instalacao`, `dimensionamento`, `fundamentos`, `calculos`, `normas`. O primeiro tópico que casa vence. Título sem indicação fica com `topic=None` — não se inventa valor.

## Hash e duplicatas

`content_hash` é o SHA-256 do `content`. Dois cortes do mesmo Markdown produzem os mesmos hashes — é o que torna a reingestão idempotente (ver [Store.md](Store.md)). A consequência simétrica: trechos byte a byte iguais dentro do mesmo documento (tabelas numéricas repetidas entre blocos de idioma) colapsam num único ponto. Esperado e benigno.

## Eventos

| Evento | Quando |
|---|---|
| `ingest.document.chunked` | Documento cortado, com `chunks` e `latency_ms` |
| `ingest.document.failed` | O corte falhou (sem perfil, sem chunks, erro interno) |

Documento que não gera nenhum chunk é falha, não resultado vazio.
