# MCP — cálculos determinísticos

Servidor [FastMCP](https://gofastmcp.com/) no workspace `mcp/` (`eletric_motor_mcp`). Arquitetura espelha [mcp-sport](https://github.com/andrequeiroz2/mcp-sport): tools finas, `schemas/`, `validators/`, `services/`, `formulas/`.

## Subir o servidor (HTTP)

```bash
# na raiz do monorepo
uv sync --all-packages
uv run --directory mcp eletric-motor-mcp
```

Variáveis (opcionais, ver `McpSettings`):

| Variável | Padrão | Descrição |
|---|---|---|
| `MCP_HOST` | `127.0.0.1` | Host HTTP |
| `MCP_PORT` | `8000` | Porta |
| `MCP_PATH` | `/mcp` | Caminho Streamable HTTP |
| `MCP_TRANSPORT` | `streamable-http` | Transporte FastMCP |
| `MCP_LOG_LEVEL` | `INFO` | Log JSON em stderr |

URL típica para clientes: `http://127.0.0.1:8000/mcp`

## Tools (Fase 2)

| Tool | Fonte | Saída |
|---|---|---|
| `calcular_corrente_nominal` | WEG guia §1.2.3–1.2.4 (FS §7.4) | `NumericToolResult` (A) |
| `calcular_queda_linha` | Método clássico (§6.2.7 verificação) | ΔU% a partir de I, R/X totais, cos φ |
| `validar_queda_nbr5410` | NBR 5410 §6.2.7 / §6.5.1.3.x | passa/não passa + limite |
| `calcular_rendimento` | WEG guia §1.2.6 | η |
| `calcular_relacao_ip_in` | WEG guia §4.5.1 (tabela kW) | I_p/I_n estimado |

Versão do conjunto de fórmulas: `formula_set_version` em cada resposta (`formulas/version.py`).

### Queda dimensional (`calcular_queda_linha`)

A NBR 5410 indexada manda **verificar** queda (§6.2.7); não há uma única equação normativa no corpo recuperado pelo RAG. O MCP usa o método clássico de instalações, com R e X **já totais** do trecho (Ω):

- **Trifásico:** \(\Delta U = \sqrt{3}\, I\, (R\cos\varphi + X\sin\varphi)\), \(\Delta U\% = 100 \cdot \Delta U / U_{linha}\)
- **Monofásico:** \(\Delta U = I\, (R\cos\varphi + X\sin\varphi)\), \(\Delta U\% = 100 \cdot \Delta U / U_{fase\text{-}neutro}\)

`comprimento_m` é metadado de projeto (v1 não deriva R/X da seção). Partida: corrente de partida e **cos φ = 0,3** (§6.5.1.3.3), depois `validar_queda_nbr5410` com contexto `partida`.

Encadeamento típico: `calcular_corrente_nominal` → `calcular_queda_linha` → `validar_queda_nbr5410`.

## Cliente RAG (`answer`)

Configure `MCP_HTTP_URL` (mesma URL acima). O CLI **não** importa fórmulas in-process; usa o cliente HTTP MCP (`mcp.Client`).

Se o MCP estiver indisponível com URL configurada, `answer` encerra com mensagem clara (não degrada silenciosamente).

## Trace no `answer`

No mesmo `trace_id` do comando `answer`, após retrieve/rerank, o stderr registra `generate.mcp.tools_called` (`mcp_tool_count`, `mcp_tool_names`) e em seguida `generate.answered`. Detalhes em [Tracing.md](Tracing.md) e [Answer.md](Answer.md).

## Docker Compose

Serviço opcional `mcp` no `compose.yaml` (porta 8000).

## Testes

```bash
uv run pytest mcp/tests
```
