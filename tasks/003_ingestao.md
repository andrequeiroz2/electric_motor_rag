# 003 — Ingestão dos PDF WEG

Task de implementação. Carrega na coleção `eletric_motor` os três PDF admitidos em [002](002_weg.md). A coleção híbrida já existe. Esta task não cria outra coleção, não consulta, não chama LLM, não usa Redis, reranker nem MCP.

A NR-10, as NBR e o guia de inversores `50029351` ficam de fora. O `50029351` não está em `data/weg/`.

Cada fase nasce pendente. Ao terminar a implementação e a verificação descritas nela, o status nesta tabela passa a `concluída`. Código escrito sem essa verificação permanece `pendente`. A fase seguinte só começa com a anterior `concluída`.

| Fase | Entrega | Status |
|---|---|---|
| 1 | Extração do guia `50032749` | concluída |
| 2 | Corte do guia `50032749` | concluída |
| 3 | Gravação do guia `50032749` | concluída |
| 4 | Pipeline completo do manual `50033244` | concluída |
| 5 | Pipeline completo do catálogo `50025536` | concluída |

O comando é `eletric-motor ingest CAMINHO`, ajuda em português, um PDF por invocação. Dado que cruza função é modelo Pydantic v2 congelado. Log com `trace_scope` e `log_event`: `ingest.document.started`, `ingest.document.completed` e `ingest.document.failed` no mesmo `trace_id`. O JSON não leva URL do Qdrant, texto integral do PDF nem texto integral de tabela.

## Regras comuns às fases 2 a 5

O Docling entrega Markdown. O primeiro corte segue os títulos. Prosa acima do limite passa pelo splitter recursivo, em tokens: 500 a 800, sobreposição 80 a 120. Tabela é um chunk inteiro, com o título da seção no início, sem sobreposição.

Cada ponto guarda `section_path`, `page`, `document_title` e `content_hash`. O `content_hash` identifica o trecho. Rodar de novo o mesmo PDF não cria outro ponto com o mesmo hash.

| Campo | Guia `50032749` | Manual `50033244` | Catálogo `50025536` |
|---|---|---|---|
| `source_type` | `guia` | `manual` | `manual` |
| `manufacturer` | `weg` | `weg` | `weg` |
| `document_id` | nome do arquivo sem `.pdf` | nome do arquivo sem `.pdf` | nome do arquivo sem `.pdf` |
| `language` | `pt-BR` | `pt-BR`, `en` ou `es`, conforme o trecho | `pt-BR` |
| `topic` | um de `fundamentos`, `dimensionamento`, `calculos`, `instalacao`, `partida`, `normas`, quando o título da seção indicar | idem | idem |
| `norm_code` | vazio | vazio | vazio |

`topic` vazio quando o título não indicar um desses seis valores. Não criar valor novo.

Vetor `dense`: `intfloat/multilingual-e5-large`, 1024, cosseno. Vetor `sparse`: `Qdrant/bm25` com modificador IDF. Nomes `dense` e `sparse`. Coleção incompatível interrompe a gravação.

Dependência nova entra no `pyproject.toml` só na fase que a importa.

## Problema conhecido — tabelas grandes mutiladas na extração

O Docling perdeu células de tabelas grandes do guia na fase 1. Exemplo: a Tabela 1.2 (correção do fator de potência) teve 924 de 926 células descartadas pelo `MatchingPostProcessor`; sobrou só uma grade 2×2. O corte da fase 2 está correto — a tabela é um chunk único com o título da seção —, mas o conteúdo desses chunks é pobre.

Avaliar na fase 3 ou 4, antes de gravar, se tratamos isso. Caminhos possíveis: ajustar o TableFormer (modo `accurate`), extrair tabelas críticas por ferramenta dedicada ou aceitar a perda e priorizar a prosa. Decisão e resultado ficam registrados aqui.

**Decisão (fase 3)**: gravar como está. A prosa, que carrega a maior parte do conteúdo do guia, está íntegra; os chunks de tabela entram mesmo pobres. O tratamento das tabelas (TableFormer `accurate` ou extração dedicada) fica para a fase 4, antes do manual — se a solução mudar o Markdown extraído, o guia é reingerido e o `content_hash` novo cria pontos novos no lugar dos antigos.

**Decisão (fase 4)**: a causa era o modo `accurate` do TableFormer, que é o default do Docling — o teste nas páginas 1 a 20 do guia mostrou o modo `fast` extraindo a Tabela 1.2 como grade 46×31 (884 células preenchidas) enquanto o `accurate` a reduzia a 2×2. O pipeline passou a fixar `TableFormerMode.FAST` em `ingest.py`. O guia foi reingerido: 191 pontos de prosa mantidos (hashes idênticos), 26 pontos de tabela substituídos. O `store.py` ganhou limpeza de pontos órfãos: após o upsert, pontos do mesmo `document_id` cujo id não está no lote atual são removidos, então a reingestão não deixa restos da extração anterior. No manual (170 tabelas) e no catálogo (grades de até 82×12) o modo `fast` perdeu no máximo 8 células por tabela.

## Fase 1 — Extração do guia

Entrada: `data/weg/weg-guia-especificacao-50032749.pdf`.

O Docling converte esse PDF em Markdown. Título de seção e número de página acompanham o trecho de onde saíram.

Verificação: um título interno conhecido do guia aparece no Markdown, com página. A contagem de páginas extraídas é maior que zero. Falha de leitura gera `ingest.document.failed` com `error_file`, `error_line` e `error_function` dentro de `eletric_motor`.

## Fase 2 — Corte do guia

Entrada: o Markdown da fase 1.

Saída: chunks do guia, com os metadados da tabela acima e com `section_path`, `page`, `document_title`, `content_hash`.

Verificação: um trecho de prosa fica entre 500 e 800 tokens. Uma tabela do guia permanece um único chunk e começa com o título da seção. Dois cortes do mesmo Markdown produzem os mesmos hashes.

## Fase 3 — Gravação do guia

Entrada: os chunks da fase 2. O Qdrant local está no ar.

Cada chunk vira um ponto com os dois vetores e o payload. O comando `eletric-motor ingest` aceita o caminho desse PDF e imprime em português quantos pontos foram gravados e quantos já existiam.

Verificação: os pontos do `document_id` `weg-guia-especificacao-50032749` estão na coleção `eletric_motor`, com vetor denso de tamanho 1024 e vetor esparso. Uma segunda execução não aumenta a contagem de pontos desse `document_id`. `ingest.document.completed` sai no mesmo `trace_id` de `ingest.document.started`.

## Fase 4 — Manual geral

O mesmo caminho das fases 1 a 3 sobre `data/weg/weg-manual-geral-iom-50033244.pdf`.

O PDF traz português, inglês e espanhol. `language` é o idioma do trecho. Trecho em inglês não fica com `pt-BR`.

Verificação: existem pontos com `document_id` `weg-manual-geral-iom-50033244` nos três idiomas. A segunda execução não duplica.

## Fase 5 — Catálogo W22

O mesmo caminho das fases 1 a 3 sobre `data/weg/weg-w22-catalogo-50025536.pdf`.

Tabela de dados elétricos ou mecânicos permanece um chunk, com o título da seção no início.

Verificação: existem pontos com `document_id` `weg-w22-catalogo-50025536`. Uma tabela amostrada não foi partida. A segunda execução não duplica.

## Critério de pronto desta task

As cinco linhas da tabela de fases estão `concluída`. Os três `document_id` coexistem na coleção `eletric_motor`. Nenhum PDF foi commitado no Git.

## Notas da execução das fases 4 e 5

- **OOM no embedding do manual**: 535 chunks de tamanhos variados levaram o processo a 27 GB e o kernel o matou. Causa: a arena de memória do onnxruntime, que reserva blocos por formato de entrada e não devolve ao SO. Correção em `embeddings.py`: `enable_cpu_mem_arena=False` nos dois modelos (RSS estável em ~9 GB). O `store.py` passou a pular o embedding de pontos já existentes (reingestão de documento igual não roda o modelo) e a intercalar embedding e upsert por lote, o que também torna a gravação retomável após falha. Metadados de trechos inalterados são atualizados via `set_payload` (contado como `points_updated`), sem reembedar — foi o que aplicou a correção de hierarquia abaixo aos 142 pontos já gravados.
- **Chunks idênticos colapsam**: trechos byte a byte iguais dentro do mesmo documento (tabelas numéricas repetidas entre blocos de idioma) têm o mesmo `content_hash` e viram um único ponto. Manual: 535 chunks → 533 pontos. Catálogo: 132 chunks → 129 pontos. Esperado e benigno.
- **Caixa "8. Recomendações adicionais:"**: o manual tem uma caixa de referência cruzada cujo título parece seção numerada; o Docling a emite como `section_header` e ela roubava a hierarquia das seções 6.x. Filtrada por documento em `_FALSE_HEADERS` no `ingest.py` (PT e ES; o bloco EN não a emite como título).
- **Processo não encerra após concluir**: o `ingest` imprime o resultado mas o processo permanece vivo (threads nativas do Docling/onnxruntime não encerram). O resultado já está gravado quando a frase sai; matar o processo é seguro. Correção fica para uma fase futura.
