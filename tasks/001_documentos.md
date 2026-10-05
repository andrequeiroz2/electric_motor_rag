# 001 — Documentos normativos

Task de requisitos. Define quais normas entram na base do Qdrant, com qual versão e com qual fonte. Não implementa ingestão.

Norma ABNT só entra com exemplar obtido no [Catálogo ABNT](https://www.abntcatalogo.com.br/). Cópia publicada em site de terceiros não é fonte. O índice guarda identificação, versão e trecho do exemplar legal. Não guarda o PDF integral reproduzido de origem não autorizada.

A NR-10 é norma regulamentadora do Ministério do Trabalho e Emprego. O texto oficial está em gov.br e pode ser carregado a partir dessa página.

## Leitura da pesquisa

A pesquisa aponta a família certa: motores de indução na ABNT NBR 17094, instalação em baixa tensão na ABNT NBR 5410, segurança do trabalho na NR-10. Três correções ficam obrigatórias antes de indexar.

A ABNT NBR 17094 não é um documento único. São quatro partes, com anos diferentes. A parte 1 de 2018, versão corrigida, cancela a ABNT NBR 17094-1:2013. A ABNT NBR 7094 foi cancelada com substituição em setembro de 2008, no mesmo mês da primeira edição da 17094-1. A edição de 2018 não é o ato que cancelou a 7094.

A ABNT NBR 5410 vigente para esta task é a edição de 30.09.2004, versão corrigida de 17.03.2008, que incorpora a Errata 1. Houve confirmações posteriores. Confirmação não é edição nova.

A NR-10 vigente nesta data não é um texto único sem prazo. A redação da Portaria SEPRT nº 915, de 30.07.2019, vale até 31.05.2027. A redação da Portaria MTE nº 737, de 29.05.2026, entra em vigor em 01.06.2027.

## Documentos admitidos

| Documento | Versão a indexar | Status | Fonte de aquisição | Papel no RAG |
|---|---|---|---|---|
| ABNT NBR 17094-1 | 2018, versão corrigida, Errata 1 de 28.05.2018. Confirmação em 12/2023 | Em vigor | [Catálogo ABNT](https://www.abntcatalogo.com.br/) | Requisitos de motores de indução trifásicos |
| ABNT NBR 17094-2 | 03/2016. Confirmação em 01/2025 | Em vigor | [Catálogo ABNT](https://www.abntcatalogo.com.br/) | Requisitos de motores de indução monofásicos |
| ABNT NBR 17094-3 | 30.04.2018, versão corrigida, Errata 1 de 30.05.2018. Confirmação em 12/2023 | Em vigor. Cancela a ABNT NBR 5383-1:2002 | [Catálogo ABNT](https://www.abntcatalogo.com.br/) | Métodos de ensaio do motor trifásico, para conformidade com a parte 1 |
| ABNT NBR 17094-4 | 03/2016 | Em vigor | [Catálogo ABNT](https://www.abntcatalogo.com.br/) | Métodos de ensaio do motor monofásico, para conformidade com a parte 2 |
| ABNT NBR 5410 | 30.09.2004, versão corrigida 17.03.2008. Confirmações em 11/2014 e 11/2018 | Em vigor. O catálogo lista `ABNT NBR 5410:2004 Versão Corrigida:2008` | [Catálogo ABNT](https://www.abntcatalogo.com.br/) | Instalações elétricas de baixa tensão, até 1000 V em corrente alternada |
| NR-10 | Portaria SEPRT nº 915, de 30.07.2019 | Vigente até 31.05.2027 | [Página oficial](https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/participacao-social/conselhos-e-orgaos-colegiados/comissao-tripartite-partitaria-permanente/normas-regulamentadora/normas-regulamentadoras-vigentes/norma-regulamentadora-no-10-nr-10) e [PDF 2019](https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/participacao-social/conselhos-e-orgaos-colegiados/comissao-tripartite-partitaria-permanente/arquivos/normas-regulamentadoras/nr-10-atualizada-2019-1.pdf) | Segurança em instalações e serviços em eletricidade |
| NR-10 | Portaria MTE nº 737, de 29.05.2026 | Vigência em 01.06.2027 | [Mesma página oficial](https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/participacao-social/conselhos-e-orgaos-colegiados/comissao-tripartite-partitaria-permanente/normas-regulamentadora/normas-regulamentadoras-vigentes/norma-regulamentadora-no-10-nr-10) e [PDF 2026](https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/participacao-social/conselhos-e-orgaos-colegiados/comissao-tripartite-partitaria-permanente/normas-regulamentadora/normas-regulamentadoras-vigentes/nr-10-atualizada-2026-1.pdf) | Texto futuro. Indexar com `valid_from` para não responder como regra atual |

Antes de comprar ou indexar cada parte da 17094, conferir de novo o registro no Catálogo ABNT. As datas de confirmação da 17094 e o cancelamento da 7094 foram lidos em fichas bibliográficas de distribuidores (Target e Busca Normas), não numa ficha pública estável do catálogo. A ficha da 5410 no catálogo, a errata de 17.03.2008 e a página do MTE são fontes diretas.

## Fora do índice

| Documento | Motivo |
|---|---|
| ABNT NBR 7094 | Cancelada com substituição em 09/2008. Não responde requisito vigente |
| ABNT NBR 17094-1:2013 e edições de 2008 | Substituídas pela 2018 versão corrigida |
| ABNT NBR 5410:1997 | Substituída pela edição de 2004 a partir de 31.03.2005 |
| PDF de norma ABNT em site universitário ou repositório aberto | Exemplar não autorizado. Não carregar |

A NR-10 não dimensiona cabo nem escolhe a categoria de conjugado. Ela manda observar as normas técnicas oficiais. Pergunta de bitola ou de rendimento usa a NBR 5410 ou a NBR 17094. Pergunta de habilitação, desenergização e trabalho em instalação usa a NR-10.

## Metadados de cada chunk

Quando a ingestão existir, cada trecho dessas fontes leva:

| Campo | Exemplo |
|---|---|
| `source_type` | `norma` |
| `manufacturer` | `abnt` para NBR; vazio para NR-10 |
| `norm_code` | `17094-1`, `5410` ou `NR-10` |
| `edition` | `2018` ou `2004` |
| `corrigenda` | `Errata 1 de 28.05.2018` ou `Versão corrigida 17.03.2008` |
| `valid_from` | `2005-03-31` na 5410; `2027-06-01` na NR-10 nova |
| `valid_until` | `2027-05-31` na NR-10 da Portaria 915/2019 |
| `language` | `pt-BR` |
| `topic` | `normas` |

Dois textos da NR-10 coexistem no acervo com vigências diferentes. A consulta da fase 3 filtra pela data de vigência. Sem esse filtro, o RAG mistura a regra de 2019 com a de 2027.

## Critério de pronto desta task

- A lista acima é a lista de carga normativa desta fase de requisitos.
- Nenhuma norma ABNT é copiada para o repositório.
- A NR-10, quando for carregada, sai só dos PDFs do gov.br citados aqui.
- Parte, ano, errata e vigência estão preenchidos antes do primeiro `ingest`.
