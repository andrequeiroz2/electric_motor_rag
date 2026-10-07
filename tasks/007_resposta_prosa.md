# 007 — Resposta em prosa (ajustes finos da saída)

Task de implementação. Refina o comando `answer`: a resposta vira texto corrido em português, sem marcadores `[n]` no corpo e sem bloco `Fontes citadas:` por padrão. O modelo continua ancorado nos trechos recuperados; só muda **como** a informação aparece para quem pergunta.

Esta task não muda coleção, ingestão, reranker, Redis nem MCP. Não antecipa warm-up de modelos, corte dinâmico de candidatos do rerank nem outras otimizações de latência — ficam no backlog ao final.

Cada fase nasce pendente. Ao terminar a implementação e a verificação descritas nela, o status nesta tabela passa a `concluída`. Código escrito sem essa verificação permanece `pendente`. A fase seguinte só começa com a anterior `concluída`.

| Fase | Entrega | Status |
|---|---|---|
| 1 | Prompt e contrato da resposta em prosa | concluída |
| 2 | Saída da CLI e flag opcional de auditoria | concluída |
| 3 | Versão do prompt no cache, docs e regressão | concluída |

## Problema (exemplo real)

Pergunta: *como podemos medir a eficiência do motor?*

**Saída atual** — resposta curta com citação inline e, depois, bloco repetindo o trecho com cabeçalho de documento:

```text
Podemos medir a eficiência do motor calculando o rendimento, ... [1].

Fontes citadas:

[1] GUIA DE ESPECIFICAÇÃO MOTORES ELÉTRICOS — 1. Noções Fundamentais › ...
    ### 1.2.6 Rendimento O rendimento define a eficiência ...
```

**Saída desejada** — um único fluxo de leitura: resposta direta e, em seguida, a definição do acervo integrada na prosa (sem `[n]`, sem lista de fontes, sem `###` colado do Markdown do chunk):

```text
Podemos medir a eficiência do motor calculando o rendimento, que é a relação entre a potência mecânica disponível no eixo (potência útil) e a potência elétrica absorvida da rede (potência absorvida).

O rendimento define a eficiência com que é feita a conversão da energia elétrica absorvida da rede pelo motor, em energia mecânica disponível no eixo. Chamando "Potência útil" P u a potência mecânica disponível no eixo e "Potência absorvida" P a a potência elétrica que o motor retira da rede, o rendimento será a relação entre as duas, ou seja:
```

O segundo parágrafo pode terminar onde o trecho original termina (inclusive fórmula incompleta no chunk), desde que venha dos trechos numerados enviados ao LLM — não inventar o que falta.

## Regras comuns às fases

- Continua valendo: só trechos recuperados, português, temperatura 0, orçamento `_fit_budget` / `LLM_CONTEXT_TOKENS`, rerank e cache como hoje.
- **Prosa, não bibliografia**: o usuário final não tem PDF; repetir título longo + caminho de seção + snippet após a resposta duplica ruído. A confiança vem da síntese no texto, não de um anexo de citações.
- **Auditoria opcional**: quem precisar conferir trechos mantém um caminho explícito na CLI (flag), não o default.
- Prompt e resposta não entram no trace; `answer_chars` e `fused_hits` permanecem.
- Mudança de prompt invalida respostas cacheadas antigas: incluir um identificador de versão do prompt na chave de cache de `answer` (junto com pergunta, filtros, limite, rerank e `llm_model`).

## Fase 1 — Prompt e contrato da resposta

Ajustar `_SYSTEM_PROMPT` (e, se necessário, instruções na mensagem humana) em `answer.py`:

- Primeiro parágrafo: resposta direta à pergunta, na primeira frase quando couber.
- Parágrafos seguintes: definir, detalhar ou contextualizar com o que os trechos trazem (definições, símbolos, relações), em prosa contínua — **sem** `[n]`, **sem** listar “fonte 1 / fonte 2”.
- Proibir conhecimento externo e manter a regra de síntese quando o valor exato não estiver nos trechos (como na task 004).
- Pedir texto limpo para terminal: evitar colar cabeçalhos Markdown (`###`) do chunk; normalizar símbolos quando o trecho usar notação quebrada (ex.: `P u` → convenção legível se o trecho permitir inferência).
- `AnswerResult` pode manter `hits` e `cited_hits`; se não houver mais `[n]` na resposta, `cited_hits` fica vazio no fluxo normal — documentar isso. Não remover o campo sem necessidade (compatibilidade com cache JSON antigo na leitura).

Verificação: com a mesma pergunta de eficiência/rendimento, a resposta **não** contém `[1]` nem a linha `Fontes citadas:` (isso é CLI na fase 2, mas o texto do LLM já deve trazer o segundo parágrafo começando por “O rendimento define…” ou equivalente fiel ao trecho).

## Fase 2 — Saída da CLI e auditoria

Em `__init__.py`, subcomando `answer`:

- **Default**: imprimir **apenas** `result.answer` (stdout), sem bloco `Fontes citadas:`.
- **Flag opcional** (nome sugerido: `--sources` ou `--show-sources`): imprime, após a resposta, a lista de trechos usados no prompt (título, caminho da seção, snippet com `_snippet`) — equivalente ao comportamento atual de auditoria, **sem** depender de `[n]` no texto do modelo. Ordem: ordem de relevância / ordem enviada ao prompt (`result.hits`), ou subconjunto documentado.

Ajuda da flag em português.

Verificação: `eletric-motor answer "como podemos medir a eficiencia do motor?"` bate visualmente com o exemplo desejado desta task (dois parágrafos, sem seção de fontes). Com `--sources`, ainda é possível inspecionar de onde veio o conteúdo.

## Fase 3 — Cache, docs e regressão

- Constante ou campo de configuração mínimo para **versão do prompt de resposta** (ex.: `answer_prompt_version=2` em `Settings` ou constante em `answer.py`) participando de `cache_key` do escopo `answer`.
- Atualizar `docs/Answer.md`, trecho relevante do README (tabela de comandos / exemplo de saída), `tasks/004_resposta.md` (nota de que o formato de citação inline + fontes foi substituído pela task 007) e, se a skill `rag-motors` descrever a saída com `[n]`, alinhar a uma linha.
- Regressão manual mínima:
  - eficiência/rendimento (prosa em dois parágrafos);
  - pergunta fora do domínio (continua recusando ou declarando falta de relação, sem inventar);
  - segunda execução igual com cache hit (`cache_scope=answer`) devolvendo o **novo** formato após miss com versão nova.

Verificação: após deploy da versão nova, uma pergunta repetida não devolve resposta antiga com `[1]` (miss na primeira vez com versão nova, hit coerente na segunda).

## Critério de pronto desta task

As três fases estão `concluída`. O default do `answer` é prosa contínua sem bloco de fontes. `--sources` restaura inspeção. Docs e chave de cache refletem a versão do prompt.

## Backlog (fora desta task)

Ideias de “mais eficiente” que **não** entram aqui, para tasks futuras se fizer sentido:

- Pré-aquecer modelos locais (processo daemon ou comando `warm-models`) para cortar os ~20 s do primeiro rerank/embed após cold start.
- `--rerank` / candidatos adaptativos quando o top-1 RRF já é dominante.
- Pós-processamento leve na resposta (normalização de fórmulas LaTeX quebradas no chunk) sem segunda chamada ao LLM.
- Modo “resposta curta” (`--brief`) vs “com definição” (default pós-007).
