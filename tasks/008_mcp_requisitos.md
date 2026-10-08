# 008 — MCP: levantamento de requisitos (fórmulas e serviço FastMCP)

Task de **especificação e implementação MCP**. Fase 0 = levantamento; fases 1–3 = código no monorepo (`mcp/` + cliente em `answer`).

| Fase | Entrega | Status |
|---|---|---|
| 0 | Levantamento: acervo, fórmulas, MCP/FastMCP, decisões de arquitetura | concluída |
| 1 | Pacote MCP no monorepo, FastMCP HTTP, esqueleto e contrato das tools | **concluída** (out/2026) |
| 2 | P0 + P1 (corrente, queda NBR, rendimento, Ip/In) com testes e rastreio de fonte | **concluída** (out/2026) |
| 3 | `answer` como cliente MCP HTTP (URL configurável; deploy do servidor indiferente) | **concluída** (out/2026) |

## Escopo do acervo analisado

| Local | Conteúdo | No RAG? |
|---|---|---|
| `data/weg/` | Guia 50032749, Manual 50033244, Catálogo W22 50025536 | **Sim** — 877 pontos na coleção `eletric_motor` |
| `data/norms/` | **NBR-5410.pdf** (`NBR-5410`) | **Sim** — 486 pontos, `norm_code=5410` (task 009) |
| `data/norms/` | NR-10 (PDFs MTE) | **Não** — fora de escopo; não ingerido |

Metodologia do levantamento: dezenas de consultas `eletric-motor query … --rerank` (out/2026) sobre corrente, queda de tensão, rendimento, potência, escorregamento e dimensionamento; leitura cruzada com [002_weg.md](002_weg.md) e metadados `topic` (`calculos`, `dimensionamento`, `instalacao`, `fundamentos`).

Limitação: o RAG devolve **trechos**; fórmulas em imagem ou equações mal extraídas pelo Docling podem aparecer **truncadas ou sem o símbolo matemático**. A implementação das tools deve fixar a expressão num **contrato versionado** (código + referência de seção), validada contra PDF quando houver dúvida.

---

## Inventário de cálculos e fórmulas no acervo ingerido

Legenda de prioridade para MCP:

- **P0** — tool já prevista no roadmap (skill `rag-motors`, README).
- **P1** — fórmula explícita ou relação clara no guia/manual; alto valor junto ao RAG.
- **P2** — tabelas, relações ou critérios (sem equação fechada única); tool auxiliar ou lookup.
- **P3** — catálogo / remissão externa; não implementar cálculo sem novos dados.

### Guia de especificação (`weg-guia-especificacao-50032749`)

| Ref. seção | Tema | O que o acervo traz | Prioridade | Tool sugerida |
|---|---|---|---|---|
| §1.2.1 | Conjugado (torque) | Definição; Nm ou % do nominal | P2 | — |
| §1.2.3–1.2.4 | Potência elétrica | Monofásico `S = U·I`; trifásico `S = √3·U·I` (texto do guia; conferir notação no PDF §1.2.4) | P1 | base de **corrente a partir de potência** |
| §1.2.5 | Fator de potência | `cos φ = P/S` (P ativa, S aparente); tabela de correção de FP | P1 | `calcular_fator_potencia` ou parâmetro de outras tools |
| §1.2.6 | Rendimento | `η = P_u / P_a` (útil vs absorvida) | P1 | `calcular_rendimento` |
| §1.5.3 | Escorregamento | Definição `s`; ligação conceitual com velocidade | P2 | — |
| §3.2.1 | Frequência 50/60 Hz | Critérios de ligação (não é uma fórmula isolada) | P3 | — |
| §4.4 | Regime de partida | Fórmula de massa-raio / inércia (trecho **incompleto** na extração: “calculados a partir da fórmula: onde: P… p…”) | P2 | exige revisão manual do PDF antes de tool |
| §4.5.1 | Corrente rotor bloqueado | **Nota explícita:** `I_p/I_n` via tabela kVA/kW × **η × cos φ**; define `I_p`, `I_n` | P1 | `calcular_relacao_ip_in` (distinto de corrente nominal) |
| §5 (p.30) | Velocidade | Relação **n**, **f**, polos **p**, escorregamento **s** (equação no trecho; símbolos no PDF) | P1 | `calcular_velocidade_sincrona` / escorregamento |
| §5.2.1 | Anéis | Perdas rotóricas, torque (equação parcial no trecho) | P3 | — |
| §7.4 | Fator de serviço | FS × potência nominal = carga contínua permissível | P2 | fator em **corrente nominal** ajustada |
| §8.3 | Potência útil T/altitude | Fatores multiplicativos (tabela) | P2 | lookup + aplicar fator |
| §11.3.2 | Inversor | Mesma família n–f–p–s | P2 | compartilhar com §5 |

### Manual geral IOM (`weg-manual-geral-iom-50033244`)

| Ref. seção | Tema | O que o acervo traz | Prioridade | Tool sugerida |
|---|---|---|---|---|
| §6.9 CONEXÃO ELÉTRICA | Dimensionamento cabos | **Critérios:** corrente nominal, FS, corrente de partida, etc.; tabelas de ligação e isolação — **não** traz equação fechada de queda % no trecho recuperado | P0 contexto | **`calcular_queda_tensao` precisa de norma ou fórmula acordada** |
| §6.13 | Métodos de partida | Tabelas partida × cabos | P2 | — |
| §6.14.5 | Cabeamento com inversor | Boas práticas | P3 | — |
| §10 Problemas × soluções | Queda / subtensão | Sintomas (tabela); reforça que queda importa na instalação | P2 | validação cruzada com tool de queda |

### Catálogo W22 (`weg-w22-catalogo-50025536`)

| Ref. seção | Tema | O que o acervo traz | Prioridade | Tool sugerida |
|---|---|---|---|---|
| §16 Dados elétricos | Placa / desempenho | **Tabelas** (In, Ip/In, Cp/Cn, J, …); texto remete a **catálogo eletrônico weg.net** para dados nominais atualizados | P2 | lookup por modelo, **não** substitui cálculo genérico |
| §3.6 / §18 | Cabos / caixas | Normas ABNT (NBR 7844 etc.), resistência de aquecimento | P3 | — |

### Síntese para as duas tools do roadmap

| Tool (roadmap) | Acervo suporta? | Proposta de requisito |
|---|---|---|
| `calcular_corrente_nominal` | **Parcial** — guia §1.2.3–1.2.5 + §7.4 (FS); manual §6.9 (lista grandezas) | Entrada: `potencia_kw`, `tensao_v`, `fase` (mono/trifásico), `rendimento`, `cos_phi`, opcional `fator_servico`. Saída: `in_a` + **referência** `document_id` + `section_path`. Fórmula trifásica padrão derivada do guia: `I_n = P_u / (√3 · U · η · cos φ)` com `P_u` em W coerente com FS. **Validar** notação exata no PDF §1.2.4 antes de codificar. |
| `calcular_queda_tensao` | Ver **§ Queda de tensão — pós NBR 5410** abaixo (task 009) | Dividir em duas tools ou duas fases da mesma entrega; não tratar como uma única fórmula fechada. |

### Queda de tensão — pós NBR 5410 (task 009)

Com `NBR-5410` indexado (`norm_code=5410`, 486 pontos), o RAG recupera **regras e limites** da instalação. O PDF confirma (texto literal, não só chunks):

| Item normativo | Conteúdo útil para MCP |
|---|---|
| **§6.2.7.1** | Limites de queda (7 % / 5 % / 7 % conforme ponto de entrega) |
| **§6.2.7.2** | Circuito terminal: queda **≤ 4 %** |
| **§6.2.7.4** | Cálculo da queda usa **corrente de projeto** |
| **§6.5.1.3.2** | Queda em **regime permanente** nos terminais do motor |
| **§6.5.1.3.3** | Na **partida**: queda no dispositivo de partida **≤ 10 %**; nota **cos φ = 0,3** (rotor bloqueado) para cálculo da queda |
| **§6.2.5 / §6.2.6** | Capacidade de condução e critérios de seção (tabelas + método de referência) |

**Tool de validação (passa/não passa)** — bem ancorada na norma: entrada `delta_u_percent` (ou tensões medidas), contexto (`regime_permanente` | `partida` | `circuito_terminal` | `instalacao_geral`), opcional `ponto_entrega`; saída `ok` / `excede` + limite aplicado + citação `NBR-5410` §6.2.7 / §6.5.1.3.x. Não inventa ΔU — só confronta valor informado com o limite.

**Tool de cálculo dimensional** (ΔU ou seção a partir de R, L, I, cabo) — **não** fechada por uma equação única no corpo da NBR 5410 indexada; a norma exige queda **verificada** e remete a **§6.2.5** (tabelas, método de referência). **Decisão de produto (task [010](010_calcular_queda_linha.md)):** v1 = **Opção A** (fórmula clássica R/X/L/I/cos φ documentada em `docs/MCP.md` + `validar_queda_nbr5410`); **Opção B** (tabelas §6.2.5 iterativas) fica backlog para dimensionamento de seção, não bloqueia ΔU%.

Manual WEG §6.9 continua como **contexto** de dimensionamento; a **autoridade de limites** para instalação BT passa a ser a 5410.

### Candidatos adicionais (backlog MCP)

| Tool | Fonte principal | Notas |
|---|---|---|
| ~~`calcular_rendimento`~~ | Guia §1.2.6 | **Fase 2** |
| ~~`calcular_relacao_ip_in`~~ | Guia §4.5.1 | **Fase 2** (tabela versionada) |
| `calcular_velocidade` | Guia §5 / §11.3.2 | n em função de f, p, s |
| `ajustar_potencia_fs` | Guia §7.4, §8.3 | FS e ambiente |
| `consultar_tabela_catalogo` | W22 §16 | Lookup, depende de dados tabulares no chunk |

---

## MCP (especificação oficial) — o que importa para este projeto

Fonte: [Model Context Protocol — Tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools) (versão 2025-06-18).

- Servidor expõe **tools** com `name`, `description`, `inputSchema` (JSON Schema); opcional `outputSchema` e `structuredContent`.
- Cliente descobre via `tools/list` e invoca via `tools/call`; erros de execução podem vir em resultado com `isError: true`.
- Tools são **controladas pelo modelo**, mas a spec recomenda **humano no loop** (confirmação, UI clara) — relevante para cálculos de instalação.
- Servidor deve **validar entradas**, controlar acesso e limitar taxa; sanitizar saídas.

Implicações para motores elétricos:

- Cada tool retorna **valor numérico + unidades + referência documental** (documento WEG, seção), não só o número.
- Schemas estritos (Pydantic v2 alinhado ao restante do repo) mapeiam para `inputSchema`/`outputSchema`.
- Erros de domínio (η > 1, tensão zero) são **tool execution errors**, não exceção opaca.

---

## FastMCP — módulo desacoplado do CLI (monorepo)

**“Serviço à parte”** aqui significa **arquitetura**, não outro repositório Git: processo HTTP (ou lib importável) separado do fluxo `eletric-motor` / Qdrant / LLM, empacotado como **módulo extraível** (fórmulas + tools) para reutilizar em outro projeto no futuro.

**Decisão (usuário): monorepo** — um único repo; layout exato na Fase 1 (ex. pacote irmão em `src/…`, workspace uv ou grupo opcional de deps) sem importar `eletric_motor.rag` nas tools v1.

Fontes: [Quickstart](https://gofastmcp.com/getting-started/quickstart), [Running Your Server](https://gofastmcp.com/v3/deployment/running-server), [The FastMCP Server](https://gofastmcp.com/v2/servers/server).

| Decisão | Proposta (Fase 1) | Motivo |
|---|---|---|
| Repositório | **Monorepo** com `eletric_motor` (RAG/CLI) + pacote MCP | Mesma revisão/versionamento; lib MCP pode ser publicada ou copiada depois |
| Framework | **FastMCP** (`uv add fastmcp`, pin de versão exata) | Decorator `@mcp.tool`, alinhado ao ecossistema MCP |
| Acoplamento | **Módulo + processo HTTP** no monorepo, **sem** importar `eletric_motor.rag` dentro das tools na v1 | Cálculo determinístico isolado do Qdrant/LLM; deploy do container/processo MCP independente do CLI |
| Transporte | **HTTP (Streamable HTTP)** em porta dedicada (ex. 8000), não stdio-only | “API à parte”: Cursor, agentes e backend consomem URL; stdio fica para dev local |
| CLI existente | `eletric-motor` **não** substituído; **`answer` chama MCP na Fase 3** (requisito) | RAG + cálculo determinístico na mesma pergunta |
| Config | Servidor: host/porta/log; cliente (`answer`, Cursor): **URL base MCP** (ex. `MCP_HTTP_URL`); **sem** `OPENAI_API_KEY` no servidor MCP v1 | Mesmo contrato HTTP se o processo roda no compose, no laptop ou noutro host — **indiferente ao monorepo** |
| Documentação de fórmulas | Módulo `formulas/` ou tabela YAML versionada (`formula_set_version`) | Desacopla OCR do RAG da verdade computacional |
| Compose | Serviço `mcp` opcional no `compose.yaml` **só quando Fase 1 autorizada** | Qdrant/Redis permanecem do RAG |

Esboço de deploy (referência, não implementar ainda):

```text
FastMCP — calcular_corrente_nominal, validar_queda_nbr5410, … (processo em qualquer host)
    ▲
    │  MCP tools/call (HTTP) — mesma URL para todos
    │
    ├── Cursor / agente / script
    └── eletric-motor answer (Fase 3) → busca Qdrant + tools/call + LLM em prosa
```

**Integração:** o RAG **não** importa o pacote MCP in-process para calcular; usa **cliente HTTP** apontando para um endereço. O código das tools pode morar no monorepo; o binário pode subir via `compose`, `uv run …` ou deploy externo — só a URL importa.

---

## Referência de implementação — [mcp-sport](https://github.com/andrequeiroz2/mcp-sport)

Repositório **do mesmo autor**: MCP de produção (FastMCP 4.x, Python 3.13, uv, Pydantic v2). Na Fase 1+ do `eletric_motor`, **arquitetura e estilo de código seguem este padrão**, adaptando domínio (fórmulas WEG/NBR, sem OpenF1).

| mcp-sport | eletric_motor (MCP) |
|---|---|
| `docs/Architectural_Design.md` | Equivalente em `docs/MCP.md` + (se necessário) `docs/MCP_Architecture.md` — thin tools, camadas |
| `docs/Technical_Reference.md` | Pin `fastmcp`, Python 3.13, links oficiais MCP/FastMCP |
| `docs/Logging_Strategy.md` | Alinhar a [traceability-logs](.cursor/skills/traceability-logs/SKILL.md); stderr/JSON; **HTTP** não usa stdout como canal de protocolo |
| `src/mcp_sport/server.py` | Entrypoint: `FastMCP(...)`, `setup_logging`, `register(mcp)` por tool |
| `tools/<recurso>.py` | `tools/calcular_corrente_nominal.py`, etc.; docstring PT-BR = interface da IA |
| `schemas/` + `BaseInput` | Entrada/saída Pydantic; saída inclui `value`, `unit`, citação documental |
| `validators/` | Regras de domínio (η ∈ (0,1], tensão > 0, contexto NBR válido) → erros legíveis |
| `services/` | Orquestra: validator → **cálculo** (não HTTP externo na v1) |
| `clients/openf1.py` | **`formulas/`** + tabelas versionadas (`formula_set`); sem Qdrant |
| stdio default + HTTP (uvicorn) para MCP Apps | **HTTP Streamable** como transporte **principal** (Fase 3 + Cursor); stdio opcional para Inspector local |
| `cache_config.py` | Opcional na v1 (fórmulas determinísticas baratas); reavaliar se tools ficarem pesadas |
| `apps/` (MCP Apps) | **Fora de escopo** v1 |

**Princípios copiados do mcp-sport** (ver [Architectural Design](https://github.com/andrequeiroz2/mcp-sport/blob/main/docs/Architectural_Design.md)):

1. Tool **thin layer** — sem regra de negócio nem fórmula inline na tool.
2. Pydantic = **forma**; validators = **semântica** de engenharia.
3. A IA **não** vê paths internos — só assinatura, docstring e schema.
4. Falhas de validação → mensagens que o modelo/cliente possam corrigir; falhas de cálculo → exceções de domínio logadas.

**Estrutura alvo (monorepo)** — espelho simplificado do mcp-sport:

```text
src/<pacote_mcp>/
├── server.py
├── logging_config.py
├── exceptions.py
├── formulas/              # verdade computacional + formula_set_version
├── schemas/
├── validators/
├── services/
└── tools/                 # register(mcp) cada tool
```

Procedimento para **nova tool** (adaptado de mcp-sport): schema → validator → service → tool → testes unitários → entrada em `docs/MCP.md`.

---

## Regras comuns às fases de implementação (futuras)

- Código das tools em **inglês**; descrições MCP em **português** (público técnico BR).
- Resultado inclui: `value`, `unit`, `formula_id`, `source_document_id`, `source_section_path`, `source_excerpt` (opcional, curto).
- **Não** commitar segredos; MCP v1 sem chaves externas.
- Testes unitários por fórmula com casos numéricos redondos + borda (FS ≠ 1).
- Atualizar `docs/` (novo `docs/MCP.md` na Fase 1) e README roadmap; skill `rag-motors` fase 7 só após Fase 2.
- NR-10 e demais PDFs em `data/norms/` **fora** das citações das tools até ingestão formal.

---

## Fase 1 — Serviço MCP (**concluída**)

Entregáveis:

1. Layout no **monorepo** conforme § [mcp-sport](https://github.com/andrequeiroz2/mcp-sport) (pacote em `src/…`, `server.py`, camadas tools/schemas/validators/services/formulas).
2. Entrypoint **HTTP** FastMCP (porta configurável); logging stderr/estruturado alinhado a [traceability-logs](.cursor/skills/traceability-logs/SKILL.md).
3. Registro de tools stub com schemas finais e `register(mcp)` por módulo.
4. `docs/MCP.md`: como subir, URL, tools, mapa fórmula → seção; apontar mcp-sport como referência de camadas.

Verificação (feita): `uv run --directory mcp eletric-motor-mcp` → `mcp.Client('http://127.0.0.1:8000/mcp').list_tools()` lista 4 tools; pacote `eletric_motor_mcp` sem import de `eletric_motor.rag`.

---

## Fase 2 — Tools P0 + P1 acordadas (**concluída**)

**P0 (roadmap README)**

1. `calcular_corrente_nominal` conforme tabela acima; validação PDF §1.2.4.
2. **`validar_queda_nbr5410`** (passa/não passa, §6.2.7 / §6.5.1.3.x). **`calcular_queda_linha`** (dimensional) **fora** desta fase (ver § Queda de tensão — pós NBR 5410).

**P1 (incluídas na mesma entrega — decisão usuário)**

3. `calcular_rendimento` — guia §1.2.6 (`η = P_u / P_a`); entradas/saídas com unidades consistentes.
4. `calcular_relacao_ip_in` — guia §4.5.1; tabela kVA/kW × **η·cos φ** versionada em `formula_set`; distinto de corrente nominal.

Verificação (feita): `uv run pytest mcp/tests` (4 testes: corrente trifásica, FS, queda partida, faixas Ip/In); respostas incluem `DocumentRef` + `formula_set_version`.

---

## Fase 3 — `answer` cliente MCP (**concluída**, requisito)

- **`eletric-motor answer`** invoca tools via **HTTP** na URL configurada (não acoplamento in-process ao pacote MCP).
- Onde o servidor FastMCP roda (container local, outro serviço, outra máquina) é **indiferente** — mesmo contrato que Cursor ou qualquer cliente MCP.
- Orquestração: LangChain tool calling ou fluxo explícito; LLM/tooling quando a pergunta pede **número**; Qdrant continua para contexto normativo e definições.
- Cache de resposta: incluir versão do `formula_set` e URL/versão MCP na chave quando tools participarem.
- Falha se MCP indisponível: **erro claro** (`SystemExit`) — ver `docs/MCP.md` e `mcp_answer.py`.

Verificação (feita): `MCP_HTTP_URL` em `Settings`; `generate_with_mcp` usa `mcp.Client`; chave de cache inclui URL + `MCP_FORMULA_SET_VERSION`; `ANSWER_PROMPT_VERSION=3`.

---

## Critério de pronto desta task (Fase 0)

- [x] Inventário de fórmulas/cálculos no acervo ingerido.
- [x] Lacunas documentadas (queda: validação 5410 OK; dimensional pendente; catálogo W22, NR-10).
- [x] Requisitos MCP oficial + FastMCP HTTP serviço separado.
- [x] Roadmap P0/P1/P2 e fases 1–3 definidas **sem código**.

## Decisões (Fase 0)

### Decididas

1. ~~**Queda de tensão (roadmap)**~~ **Decidido (task 009 + § Queda de tensão — pós NBR 5410).** Ingestão 5410 feita. P0: **`validar_queda_nbr5410`** (passa/não passa, §6.2.7, §6.5.1.3.x). **`calcular_queda_linha`** (dimensional) só depois, com método externo documentado ou fluxo §6.2.5 — **não** uma tool genérica `calcular_queda_tensao`.
2. ~~**Monorepo vs repo separado**~~ **Decidido: monorepo.** MCP = módulo/lib (extraível) + serviço HTTP; “à parte” = desacoplamento do RAG/CLI, não repo Git separado.
3. ~~**Escopo Fase 2**~~ **Decidido: P0 + ambos P1** — `calcular_corrente_nominal`, `validar_queda_nbr5410`, `calcular_rendimento`, `calcular_relacao_ip_in` (sem `calcular_queda_linha` nesta fase).
4. ~~**Integração Fase 3**~~ **Decidido: requisito.** O `answer` chama MCP por **endereço HTTP**; Cursor/outros clientes usam a mesma URL. **Indiferente** se o processo FastMCP é “dentro do projeto” (compose/`uv run`) ou remoto — só importa a URL configurada, não import Python direto das tools no `answer`.
5. **Referência de código:** [andrequeiroz2/mcp-sport](https://github.com/andrequeiroz2/mcp-sport) — padrão arquitetural e de implementação (FastMCP 4, camadas thin tool / service / validator / schema); ver § Referência de implementação acima.

### Em aberto (antes da Fase 1)

_Nenhuma decisão de arquitetura MCP pendente na Fase 0._
