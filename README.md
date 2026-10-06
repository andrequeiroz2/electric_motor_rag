# eletric_motor

![Python](https://img.shields.io/badge/Python-3.13%2B-3776AB?logo=python&logoColor=white)
![uv](https://img.shields.io/badge/uv-pacotes-DE5FE9?logo=uv&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-orquestra%C3%A7%C3%A3o-1C3C3C?logo=langchain&logoColor=white)
![Qdrant](https://img.shields.io/badge/Qdrant-busca%20h%C3%ADbrida-DC244C)
![OpenAI](https://img.shields.io/badge/OpenAI-gpt--4o-412991?logo=openai&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

RAG de documentação técnica de motores elétricos. Pergunte em português — o sistema busca nos PDFs do acervo (manuais, guias e catálogos WEG) e responde com citação da fonte, da seção e do trecho original.

## O que ele faz

- **Ingere PDFs técnicos**: extrai texto e tabelas com Docling, corta em chunks por seção (prosa de 500–800 tokens, tabela inteira em um chunk) e grava no Qdrant com metadados (tipo de fonte, fabricante, tópico, idioma).
- **Busca híbrida**: vetor denso (`intfloat/multilingual-e5-large`, 1024 dimensões) + vetor esparso (BM25) fundidos com RRF. Filtros por metadado quando a pergunta pede.
- **Responde com citação**: o LLM (gpt-4o) responde só com base nos trechos recuperados, cita `[n]` em cada afirmação e a CLI mostra o texto das fontes citadas — sem precisar abrir o PDF.
- **Rastreável**: cada operação emite eventos JSON no stderr com `trace_id` único, da busca à resposta (ver [docs/Tracing.md](docs/Tracing.md)).
- **Idempotente**: reingerir o mesmo PDF não duplica pontos; metadados mudados são atualizados sem reembedar.

## Arquitetura

```text
PDF ──► Docling (Markdown) ──► chunk por seção ──► embeddings ──► Qdrant
                                      │              dense + sparse
pergunta ──► busca híbrida (RRF) ──► 16 trechos ──► gpt-4o ──► resposta + fontes
                 │                                                  │
                 └────────── trace JSON no stderr (trace_id) ◄──────┘
```

## Estrutura

```text
├── compose.yaml              # Qdrant local
├── pyproject.toml            # Python 3.13+, dependências via uv
├── data/
│   ├── weg/                  # PDFs WEG (não versionados)
│   └── norms/                # Normas (não versionados)
├── docs/
│   ├── Tracing.md            # Referência do log estruturado
│   └── Settings.md           # Referência da configuração
├── src/eletric_motor/
│   ├── __init__.py           # CLI: init-collection, ingest, query, answer
│   └── rag/
│       ├── collection.py     # Criação idempotente da coleção híbrida
│       ├── ingest.py         # Extração Docling (TableFormer fast)
│       ├── chunk.py          # Corte por seção, idioma, tópico
│       ├── embeddings.py     # fastembed: e5-large denso + BM25 esparso
│       ├── store.py          # Upsert idempotente, refresh de payload
│       ├── search.py         # Busca híbrida com fusão RRF
│       ├── answer.py         # Prompt, chamada ao LLM, fontes citadas
│       ├── settings.py       # Configuração via ambiente/.env
│       └── trace.py          # Log JSON estruturado
└── tasks/                    # Specs de cada fase implementada
```

## Tecnologias

| Peça | Uso |
|---|---|
| Python 3.13 + uv | Linguagem e gerenciador de pacotes |
| Qdrant (Docker) | Banco vetorial, coleção híbrida densa + esparsa |
| Docling | Extração de PDF para Markdown (tabelas em modo fast) |
| fastembed | Embeddings locais: e5-large (denso) e BM25 (esparso) |
| LangChain + langchain-openai | Orquestração e chamada ao gpt-4o |
| Pydantic v2 | Modelos congelados e validação de configuração |

## Pré-requisitos

- Python 3.13+ e [uv](https://docs.astral.sh/uv/)
- Docker (para o Qdrant)
- Chave da OpenAI (só para o comando `answer`)

## Como rodar

```bash
# 1. Instalar dependências
uv sync

# 2. Subir o Qdrant
docker compose up -d

# 3. Configurar a chave (para respostas com LLM)
echo "OPENAI_API_KEY=sk-..." > .env

# 4. Criar a coleção (idempotente)
uv run eletric-motor init-collection

# 5. Ingerir um PDF
uv run eletric-motor ingest data/weg/weg-manual-geral-iom-50033244.pdf

# 6. Perguntar
uv run eletric-motor answer "como dimensionar condutores para motor trifásico"
```

## Uso

| Comando | O que faz |
|---|---|
| `init-collection` | Cria ou confere a coleção híbrida e os índices de payload |
| `ingest CAMINHO` | Extrai um PDF, corta em chunks e grava na coleção |
| `query PERGUNTA` | Lista os trechos mais relevantes (sem LLM, não gasta API) |
| `answer PERGUNTA` | Responde com o LLM e lista as fontes citadas com o texto |

`query` e `answer` aceitam filtros: `--source-type manual|guia`, `--manufacturer weg`, `--topic instalacao`, `--language pt-BR`, `--limit N` (padrão 8 no `query`, 16 no `answer`).

```bash
uv run eletric-motor answer "como calcular a corrente de rotor bloqueado" --source-type guia
```

## Configuração

Variáveis de ambiente ou arquivo `.env` (não versionado):

| Variável | Padrão | Função |
|---|---|---|
| `OPENAI_API_KEY` | — | Chave da OpenAI (obrigatória para `answer`) |
| `LLM_MODEL` | `gpt-4o` | Modelo da resposta |
| `QDRANT_URL` | `http://localhost:6333` | Endereço do Qdrant |
| `QDRANT_COLLECTION` | `eletric_motor` | Nome da coleção |
| `EMBEDDING_THREADS` | todos os núcleos | Limite de CPU do embedding local |

Referência completa em [docs/Settings.md](docs/Settings.md).

## Observabilidade

A resposta vai para o stdout; o trace JSON vai para o stderr. Para inspecionar:

```bash
uv run eletric-motor answer "..." 2> trace.log
```

Cada execução gera eventos com o mesmo `trace_id`: `retrieve.hybrid.completed` (busca) e `generate.answered` (resposta), com contagens, filtros e latência. Formato e campos em [docs/Tracing.md](docs/Tracing.md).

## Roadmap

- [x] Coleção híbrida no Qdrant
- [x] Ingestão de PDFs (Docling, chunking, dois vetores)
- [x] Consulta híbrida com filtro de metadado
- [x] Resposta do LLM com citação de fonte e seção
- [ ] Redis: cache de embedding e de resposta
- [ ] Reranker `bge-reranker-v2-m3`
- [ ] MCP: `calcular_corrente_nominal` e `calcular_queda_tensao`

## Notas

- Os PDFs em `data/` e o arquivo `.env` não são versionados.
- O catálogo impresso da linha W22 não traz as tabelas de dados elétricos (a WEG aponta para o catálogo eletrônico); perguntas por valores nominais de um modelo específico dependem de ingestão futura desses dados.
