import json
import re
import time
from functools import cache

import tiktoken
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict

from eletric_motor.rag.cache import cache_get, cache_key, cache_set
from eletric_motor.rag.chunk import Chunk
from eletric_motor.rag.search import SearchFilters, SearchHit, search_chunks
from eletric_motor.rag.settings import Settings
from eletric_motor.rag.trace import (
    TraceContext,
    bind_trace,
    elapsed_ms,
    error_message,
    error_origin,
    log_event,
    release_trace,
)

# Incrementar quando o contrato de saída mudar; entra na chave de cache de resposta.
ANSWER_PROMPT_VERSION = 2

_SYSTEM_PROMPT = (
    "Você responde perguntas sobre motores elétricos usando apenas os trechos "
    "numerados da documentação técnica fornecida. Regras: responda em "
    "português, em prosa contínua para leitura no terminal; não use "
    "marcadores [n], listas numeradas de fontes nem cabeçalhos Markdown "
    "(###) copiados dos trechos; não use conhecimento fora dos trechos. "
    "Primeiro parágrafo: resposta direta à pergunta, já na primeira frase "
    "quando couber. Parágrafos seguintes: defina, detalhe ou contextualize "
    "com o que os trechos trazem (definições, símbolos, relações), "
    "integrando o texto de forma natural — sem dizer “fonte 1” ou “trecho 2”. "
    "Se o valor exato pedido não estiver nos trechos, não se limite a dizer "
    "que falta: explique o que a documentação oferece — como obter ou calcular "
    "o valor, onde aparece. Só diga que a documentação não cobre o ponto "
    "quando nenhum trecho tiver relação com a pergunta. Normalize símbolos "
    "quebrados nos trechos (ex.: P u → P_u) quando o sentido for claro."
)


_CITATION = re.compile(r"\[(\d+)\]")

# Tabelas entram no prompt inteiras; sem teto, uma grade grande estoura a cota
# de tokens da API. Acima disso, o trecho é truncado com marcador.
_CHUNK_TOKEN_LIMIT = 2000
_TRUNCATION_MARK = "\n[... trecho truncado ...]"


class AnswerResult(BaseModel, frozen=True):
    model_config = ConfigDict(extra="forbid")

    answer: str
    hits: tuple[SearchHit, ...]
    llm_model: str

    @property
    def cited_hits(self) -> tuple[SearchHit, ...]:
        """Hits whose [n] appears in the answer; empty when the model uses prose only."""
        order = {
            int(n): i for i, n in enumerate(_CITATION.findall(self.answer))
        }
        cited = [
            (rank, hit)
            for rank, hit in enumerate(self.hits, start=1)
            if rank in order
        ]
        cited.sort(key=lambda item: order[item[0]])
        return tuple(hit for _, hit in cited)


def answer_question(
    question: str,
    filters: SearchFilters | None = None,
    limit: int = 16,
    rerank: bool = True,
    use_cache: bool = True,
) -> AnswerResult:
    token = bind_trace()
    started = time.perf_counter()
    settings = Settings()
    filters = filters or SearchFilters()
    if settings.openai_api_key is None:
        release_trace(token)
        raise SystemExit(
            "Configure OPENAI_API_KEY no ambiente ou no arquivo .env para "
            "gerar respostas."
        )
    key = cache_key(
        "answer",
        question,
        json.dumps(filters.active(), sort_keys=True),
        str(limit),
        str(rerank),
        settings.llm_model,
        str(ANSWER_PROMPT_VERSION),
    )
    cached = cache_get("answer", key, enabled=use_cache)
    if cached is not None:
        release_trace(token)
        return AnswerResult.model_validate_json(cached)
    try:
        result = search_chunks(
            question, filters, limit=limit, rerank=rerank, use_cache=use_cache
        )
        answer, prompt_hits = _generate(question, result.hits, settings)
    except SystemExit:
        raise
    except Exception as exc:
        _log_failed(exc, started, settings)
        raise SystemExit("Não consegui gerar a resposta.") from exc
    else:
        log_event(
            "generate.answered",
            logger_name=__name__,
            context=TraceContext(
                span="generate",
                collection=settings.collection_name,
                filters=filters.active() or None,
                fused_hits=len(prompt_hits),
                llm_model=settings.llm_model,
                answer_chars=len(answer),
                latency_ms=elapsed_ms(started),
            ),
        )
        outcome = AnswerResult(
            answer=answer, hits=prompt_hits, llm_model=settings.llm_model
        )
        cache_set("answer", key, outcome.model_dump_json(), enabled=use_cache)
        return outcome
    finally:
        release_trace(token)


def _generate(
    question: str, hits: tuple[SearchHit, ...], settings: Settings
) -> tuple[str, tuple[SearchHit, ...]]:
    fitted = _fit_budget(hits, settings.llm_context_tokens)
    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=0,
        api_key=settings.openai_api_key,
    )
    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=_user_prompt(question, fitted)),
    ]
    response = llm.invoke(messages)
    return str(response.content), fitted


def _fit_budget(hits: tuple[SearchHit, ...], budget: int) -> tuple[SearchHit, ...]:
    """Keep the best hits that fit the token budget; truncate huge chunks."""
    fitted: list[SearchHit] = []
    spent = 0
    for hit in hits:
        chunk = hit.chunk
        tokens = _encoder().encode(chunk.content)
        if len(tokens) > _CHUNK_TOKEN_LIMIT:
            chunk = chunk.model_copy(
                update={
                    "content": _encoder().decode(tokens[:_CHUNK_TOKEN_LIMIT])
                    + _TRUNCATION_MARK
                }
            )
        cost = len(_encoder().encode(_block(len(fitted) + 1, chunk)))
        if spent + cost > budget:
            break
        spent += cost
        fitted.append(SearchHit(score=hit.score, chunk=chunk))
    return tuple(fitted)


def _user_prompt(question: str, hits: tuple[SearchHit, ...]) -> str:
    sources = "\n\n".join(
        _block(rank, hit.chunk) for rank, hit in enumerate(hits, start=1)
    )
    return (
        f"Pergunta: {question}\n\n"
        "Trechos da documentação (referência interna; não cite [n] na resposta):\n\n"
        f"{sources}\n\n"
        "Escreva a resposta em um ou mais parágrafos de prosa, sem [n]."
    )


def _block(rank: int, chunk: Chunk) -> str:
    section = " › ".join(chunk.section_path)
    return (
        f"[{rank}] {chunk.document_title} — {section} — p.{chunk.page}\n"
        f"{chunk.content}"
    )


@cache
def _encoder() -> tiktoken.Encoding:
    return tiktoken.get_encoding("cl100k_base")


def _log_failed(exc: BaseException, started: float, settings: Settings) -> None:
    origin = error_origin(exc)
    log_event(
        "generate.failed",
        level="error",
        logger_name=__name__,
        context=TraceContext(
            span="generate",
            collection=settings.collection_name,
            llm_model=settings.llm_model,
            latency_ms=elapsed_ms(started),
            error_type=type(exc).__name__,
            error_message=error_message(exc),
            error_file=None if origin is None else origin[0],
            error_line=None if origin is None else origin[1],
            error_function=None if origin is None else origin[2],
        ),
    )
