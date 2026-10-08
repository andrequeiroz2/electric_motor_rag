# 010 — MCP: `calcular_queda_linha` (queda dimensional)

Complementa [008](008_mcp_requisitos.md) e [009](009_ingestao_nbr5410.md). A tool **`validar_queda_nbr5410`** cobre passa/não passa; **`calcular_queda_linha`** calcula ΔU% antes da validação (Opção A, v1).

## Decisão recomendada: **Opção A (v1)** — fórmula clássica documentada

| Critério | Opção A — fórmula clássica | Opção B — tabelas §6.2.5 iterativas |
|---|---|---|
| **Precisão do ΔU%** | Alta **se** R/X (ou seção + método) forem corretos; erro vem dos dados de cabo, não da álgebra | ΔU usa mesma física no fim; “precisão normativa” extra é na **seção** (ampacidade), não numa fórmula mágica diferente |
| **Aderência literal à 5410** | Norma manda **verificar** queda; não indexamos equação única no corpo — método externo citado em `docs/MCP.md` | Maior alinhamento ao fluxo “tabela → seção → verificar queda”, porém §6.2.5 exige **tabelas grandes** (método de instalação, agrupamento, temperatura, etc.) |
| **Risco de erro no produto** | Baixo: poucas entradas, fórmula estável, testes numéricos fechados | Alto: OCR/tabelas incompletas no RAG, versionamento pesado, escopo de **dimensionamento de cabo**, não só ΔU |
| **Encadeamento MCP atual** | Natural: `calcular_corrente_nominal` → `calcular_queda_linha` → `validar_queda_nbr5410` | Exige motor de iteração + lookup normativo antes do ΔU |
| **Esforço** | Uma tool + `formula_set` | Subsistema de tabelas + loop + testes por método de referência |

**Conclusão:** para **precisão do cálculo de queda** (valor de ΔU%), a opção **A** é a melhor relação correção/incerteza: a incerteza dominante é sempre **R, X, L e I** (e cos φ na partida), não a forma da norma de limites. A opção **B** melhora sobretudo **escolha de seção** conforme ampacidade; é **fase 2** opcional (`dimensionar_secao_nbr5410`), não substituto obrigatório da fórmula de ΔU.

**Opção C** (só validação) permanece válida quem já tem ΔU medido/calculado externamente.

## Escopo v1 — `calcular_queda_linha` (Opção A)

### Propósito

Calcular **queda de tensão percentual** em trecho de linha BT, com referência documental explícita de que a NBR 5410 exige **verificação** (§6.2.7), não reprodução literal de um único artigo algébrico.

### Entradas (proposta)

| Campo | Tipo | Notas |
|---|---|---|
| `corrente_a` | float | Corrente de projeto (regime ou partida; ver §6.2.7.4 / §6.5.1.3.3) |
| `comprimento_m` | float | Comprimento do trecho (m) |
| `tensao_v` | float | Tensão nominal de referência (linha trifásica ou fase mono) |
| `fase` | `monofasico` \| `trifasico` | Define fator √3 e interpretação de U |
| `cos_phi` | float | Regime permanente; **0,3** na partida (nota §6.5.1.3.3) se contexto partida |
| `resistencia_ohm` | float | **Opcional** — resistência total do trecho (Ω) |
| `reatancia_ohm` | float | **Opcional** — reatância total do trecho (Ω); default 0 se omitida |
| `secao_mm2` + `material` + `metodo` | lookup futuro | **v1.1** — derivar R/X de tabela reduzida; **fora** do v1 mínimo |

**v1 mínimo:** usuário (ou LLM via outra fonte) informa **`resistencia_ohm`** (e opcionalmente **`reatancia_ohm`**) já calculados para o trecho, ou informa R′ por km × L se a tool aceitar `resistividade_linha_ohm` — decidir na implementação entre “R total” vs “R′/km + L” (preferir **R total + X total** para menos ambiguidade).

### Fórmula (contrato `formula_set`, a validar no PDF de engenharia de referência)

Trifásico, queda de tensão na linha (valor usual em instalações):

\[
\Delta U = \sqrt{3}\, I\, (R \cos\varphi + X \sin\varphi)
\]

\[
\Delta U\% = 100 \cdot \frac{\Delta U}{U_{nom}}
\]

Monofásico (**fixado na implementação**): R/X totais do trecho (ida+volta), \(U_{ref}\) fase-neutro:

\[
\Delta U = I\, (R \cos\varphi + X \sin\varphi)
\]

Saída: `NumericToolResult` com `value` = ΔU%, `unit` = `%`, mais `DocumentRef` (`formula_id=line_voltage_drop_pct`, norma §6.2.7 verificação + referência do método em `docs/MCP.md`).

### Encadeamento

1. `calcular_queda_linha` → ΔU%
2. `validar_queda_nbr5410` → passa/não passa com mesmo `contexto`

### Precisão — expectativa honesta

- **±0,1–0,5 %** ou melhor se R, X, I, cos φ forem de placa/projeto e R/X de catálogo de cabo (NBR 7286 / fabricante).
- **Não** substitui projeto elétrico completo: harmonics, temperatura, agrupamento e ampacidade ficam fora do v1.
- Partida: usar **I partida** (de placa ou `calcular_corrente_nominal` × Ip/In) e **cos φ = 0,3** quando contexto for §6.5.1.3.3.

## Backlog — Opção B (fase posterior)

Tool separada, ex. `dimensionar_secao_nbr5410` ou extensão iterativa:

- Entrada: corrente, método de referência, temperatura, agrupamento, material.
- Uso das tabelas §6.2.5 / §6.2.6 versionadas em YAML (fora do RAG).
- Loop: candidato de seção → R/X → `calcular_queda_linha` → `validar_queda_nbr5410`.

Só iniciar após **digitizar e validar** tabelas contra PDF (como Ip/In no guia WEG).

## Critério de pronto da implementação

- [x] `formulas/line_voltage_drop.py` + testes com caso numérico manual (mono e trifásico).
- [x] Tool MCP + service + citação §6.2.7 (verificação) + método em `docs/MCP.md`.
- [x] `formula_set_version` → `2026.04.1` (`mcp_answer.MCP_FORMULA_SET_VERSION` alinhado).
- [x] Teste de encadeamento: 10 kW → In → ΔU% → `validar_queda_nbr5410`.

## Status

| Fase | Entrega | Status |
|---|---|---|
| 0 | Análise A vs B e decisão A para v1 | concluída |
| 1 | Implementação MCP + docs + testes | concluída |
