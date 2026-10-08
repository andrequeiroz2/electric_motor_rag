# 009 — Ingestão da ABNT NBR 5410:2004 VC 2008

Task de implementação. Indexa o exemplar local `data/norms/NBR-5410.pdf` na coleção `eletric_motor`, com metadados de norma. Não implementa MCP.

| Fase | Entrega | Status |
|---|---|---|
| 1 | Perfil em `chunk.py` e ajustes de extração em `ingest.py` | concluída |
| 2 | `ingest` do PDF e verificação de busca com `--norm-code 5410` | concluída |

## Metadados

| Campo | Valor |
|---|---|
| `document_id` | `NBR-5410` (stem do arquivo) |
| `source_type` | `norma` |
| `manufacturer` | `abnt` |
| `norm_code` | `5410` |
| `language` | `pt-BR` |

## Comando

```bash
uv run eletric-motor ingest data/norms/NBR-5410.pdf
```

Verificação: `uv run eletric-motor query "queda de tensão circuito terminal motor" --norm-code 5410 --limit 5 --rerank` retorna trechos da norma.

## Resultado da ingestão (2026-10-07)

- 217 páginas Docling, 404 seções, **486 chunks** (400 prosa, 86 tabelas), **486 pontos** novos na coleção (total acervo ≈ 877 + 486).
- Extração ~26 min; gravação/embed ~8,5 min.
