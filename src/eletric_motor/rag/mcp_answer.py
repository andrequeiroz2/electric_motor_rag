"""Generate answers with MCP tool calling over HTTP (Fase 3)."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from mcp import Client

from eletric_motor.rag.answer import _fit_budget, _user_prompt
from eletric_motor.rag.search import SearchHit
from eletric_motor.rag.settings import Settings
from eletric_motor.rag.trace import TraceContext, elapsed_ms, log_event

# Mantido alinhado a mcp/src/eletric_motor_mcp/formulas/version.py
MCP_FORMULA_SET_VERSION = "2026.04.1"

_MCP_SYSTEM_ADDendum = (
    " Quando a pergunta exigir valores numéricos (corrente, rendimento, relação Ip/In, "
    "validação de queda de tensão), use as ferramentas MCP disponíveis antes de concluir. "
    "Integre o resultado das ferramentas na prosa, com unidades, sem inventar números."
)

_MAX_TOOL_ROUNDS = 6


def generate_with_mcp(
    question: str, hits: tuple[SearchHit, ...], settings: Settings
) -> tuple[str, tuple[SearchHit, ...]]:
    url = settings.mcp_http_url
    if url is None:
        raise RuntimeError("MCP_HTTP_URL não configurada.")
    started = time.perf_counter()
    try:
        answer, fitted, tool_names = asyncio.run(_generate_async(question, hits, settings))
    except Exception as exc:
        detail = _root_error_message(exc)
        raise SystemExit(
            f"Não consegui usar o servidor MCP em {url}. Verifique se ele está no ar "
            f"(uv run --directory mcp eletric-motor-mcp). Detalhe: {detail}"
        ) from exc
    log_event(
        "generate.mcp.tools_called",
        logger_name=__name__,
        context=TraceContext(
            span="generate",
            mcp_tool_count=len(tool_names),
            mcp_tool_names=tool_names,
            latency_ms=elapsed_ms(started),
        ),
    )
    return answer, fitted


async def _generate_async(
    question: str, hits: tuple[SearchHit, ...], settings: Settings
) -> tuple[str, tuple[SearchHit, ...], tuple[str, ...]]:
    fitted = _fit_budget(hits, settings.llm_context_tokens)
    tool_names: list[str] = []
    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=0,
        api_key=settings.openai_api_key,
    )
    assert settings.mcp_http_url is not None
    async with Client(settings.mcp_http_url) as client:
        listed = await client.list_tools()
        openai_tools = [_tool_schema(tool) for tool in listed.tools]
        messages: list[Any] = [
            SystemMessage(content=_system_with_mcp()),
            HumanMessage(content=_user_prompt(question, fitted)),
        ]
        for _ in range(_MAX_TOOL_ROUNDS):
            bound = llm.bind_tools(openai_tools) if openai_tools else llm
            response = await bound.ainvoke(messages)
            messages.append(response)
            if not isinstance(response, AIMessage) or not response.tool_calls:
                return str(response.content), fitted, tuple(tool_names)
            for call in response.tool_calls:
                name = call["name"]
                tool_names.append(name)
                args = call.get("args") or {}
                result = await client.call_tool(name, args)
                payload = _format_tool_result(result)
                messages.append(
                    ToolMessage(content=payload, tool_call_id=call["id"])
                )
        raise RuntimeError("Limite de chamadas MCP atingido sem resposta final.")


def _system_with_mcp() -> str:
    from eletric_motor.rag.answer import _SYSTEM_PROMPT

    return _SYSTEM_PROMPT + _MCP_SYSTEM_ADDendum


def _tool_schema(tool: Any) -> dict[str, Any]:
    schema = getattr(tool, "input_schema", None) or {"type": "object", "properties": {}}
    if hasattr(schema, "model_dump"):
        schema = schema.model_dump(exclude_none=True)
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": schema,
        },
    }


def _root_error_message(exc: BaseException) -> str:
    if isinstance(exc, BaseExceptionGroup):
        for sub in exc.exceptions:
            return _root_error_message(sub)
    return str(exc)


def _format_tool_result(result: Any) -> str:
    structured = getattr(result, "structured_content", None) or getattr(
        result, "structuredContent", None
    )
    if structured is not None:
        return json.dumps(structured, ensure_ascii=False)
    if hasattr(result, "content") and result.content:
        parts = []
        for block in result.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        if parts:
            return "\n".join(parts)
    return json.dumps(result.model_dump() if hasattr(result, "model_dump") else str(result))
