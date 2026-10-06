import re
import time

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict

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

_SYSTEM_PROMPT = (
    "Você responde perguntas sobre motores elétricos usando apenas os trechos "
    "numerados da documentação técnica fornecida. Regras: responda em "
    "português; seja direto, entregando a resposta já na primeira frase; "
    "baseie cada afirmação nos trechos e cite a fonte ao final da frase no "
    "formato [n]; não use conhecimento fora dos trechos. Se o valor exato "
    "pedido não estiver nos trechos, não se limite a dizer que falta: "
    "explique o que a documentação oferece sobre o tema — como obter ou "
    "calcular o valor, onde ele aparece — citando as fontes. Só diga que a "
    "documentação não cobre o ponto quando nenhum trecho tiver relação com a "
    "pergunta."
)


_CITATION = re.compile(r"\[(\d+)\]")


class AnswerResult(BaseModel, frozen=True):
    model_config = ConfigDict(extra="forbid")

    answer: str
    hits: tuple[SearchHit, ...]
    llm_model: str

    @property
    def cited_hits(self) -> tuple[SearchHit, ...]:
        """Hits whose [n] number appears in the answer text, in answer order."""
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
    try:
        result = search_chunks(question, filters, limit=limit, rerank=rerank)
        answer = _generate(question, result.hits, settings)
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
                fused_hits=len(result.hits),
                llm_model=settings.llm_model,
                answer_chars=len(answer),
                latency_ms=elapsed_ms(started),
            ),
        )
        return AnswerResult(answer=answer, hits=result.hits, llm_model=settings.llm_model)
    finally:
        release_trace(token)


def _generate(question: str, hits: tuple[SearchHit, ...], settings: Settings) -> str:
    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=0,
        api_key=settings.openai_api_key,
    )
    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=_user_prompt(question, hits)),
    ]
    response = llm.invoke(messages)
    return str(response.content)


def _user_prompt(question: str, hits: tuple[SearchHit, ...]) -> str:
    blocks = []
    for rank, hit in enumerate(hits, start=1):
        chunk = hit.chunk
        section = " › ".join(chunk.section_path)
        blocks.append(
            f"[{rank}] {chunk.document_title} — {section} — p.{chunk.page}\n"
            f"{chunk.content}"
        )
    sources = "\n\n".join(blocks)
    return f"Pergunta: {question}\n\nTrechos da documentação:\n\n{sources}"


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
