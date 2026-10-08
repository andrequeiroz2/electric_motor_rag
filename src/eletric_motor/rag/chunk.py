from __future__ import annotations

import hashlib
import re
import time
from functools import cache
from typing import TYPE_CHECKING, Literal

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langdetect import DetectorFactory, detect
from langdetect.lang_detect_exception import LangDetectException
from pydantic import BaseModel, ConfigDict, Field

from eletric_motor.rag.trace import (
    TraceContext,
    bind_trace,
    elapsed_ms,
    error_message,
    error_origin,
    log_event,
    release_trace,
)

if TYPE_CHECKING:
    from eletric_motor.rag.ingest import DocumentSection, ExtractedDocument

# O limite de tokens da prosa é medido no cl100k_base, tokenizador de referência do projeto.
_PROSE_CHUNK_SIZE = 800
_PROSE_CHUNK_OVERLAP = 100
_PROSE_WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]{3,}")

Topic = Literal["fundamentos", "dimensionamento", "calculos", "instalacao", "partida", "normas"]

# Palavras-chave do título da seção que indicam o tópico, em ordem de prioridade.
_TOPIC_KEYWORDS: tuple[tuple[Topic, tuple[str, ...]], ...] = (
    ("partida", ("partida", "acelera", "starting", "arranque")),
    ("instalacao", ("instala", "installation", "montagem", "mounting", "ambiente", "ambiental")),
    ("dimensionamento", ("dimensionamento", "seleção", "aplicação")),
    ("fundamentos", ("fundament",)),
    ("calculos", ("cálculo", "calculo")),
    ("normas", ("norma",)),
)

# O langdetect é randômico sem seed; o idioma precisa ser estável entre reingestões.
DetectorFactory.seed = 0
_LANGUAGE_MAP = {"pt": "pt-BR", "en": "en", "es": "es"}
# Trechos longos não mudam o veredito e só tornam a detecção lenta.
_LANGUAGE_SAMPLE = 3000


class DocumentProfile(BaseModel, frozen=True):
    model_config = ConfigDict(extra="forbid")

    source_type: Literal["manual", "norma", "guia"]
    manufacturer: str = Field(min_length=1)
    language: str = Field(min_length=1)
    # True: o idioma é detectado por seção (manual trilíngue); `language` vira o fallback.
    detect_language: bool = False
    # Normas ABNT: filtro `norm_code` na busca (ex.: 5410).
    norm_code: str | None = None


# Metadados fixos de cada PDF admitido; documento fora desta lista não é ingerido.
_DOCUMENTS: dict[str, DocumentProfile] = {
    "weg-guia-especificacao-50032749": DocumentProfile(
        source_type="guia", manufacturer="weg", language="pt-BR"
    ),
    "weg-manual-geral-iom-50033244": DocumentProfile(
        source_type="manual", manufacturer="weg", language="pt-BR", detect_language=True
    ),
    "weg-w22-catalogo-50025536": DocumentProfile(
        source_type="manual", manufacturer="weg", language="pt-BR"
    ),
    "NBR-5410": DocumentProfile(
        source_type="norma",
        manufacturer="abnt",
        language="pt-BR",
        norm_code="5410",
    ),
}


class Chunk(BaseModel, frozen=True):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    document_title: str = Field(min_length=1)
    section_path: tuple[str, ...] = Field(min_length=1)
    page: int = Field(ge=1)
    kind: Literal["prose", "table"]
    content: str = Field(min_length=1)
    content_hash: str = Field(min_length=64, max_length=64)
    tokens: int = Field(ge=1)
    source_type: str = Field(min_length=1)
    manufacturer: str = Field(min_length=1)
    language: str = Field(min_length=1)
    topic: Topic | None = None
    norm_code: str | None = None


def chunk_document(document: ExtractedDocument) -> tuple[Chunk, ...]:
    token = bind_trace()
    started = time.perf_counter()
    try:
        chunks = _chunk(document)
    except SystemExit as exc:
        if token is not None:
            _log_failed(document.document_id, exc, started)
        raise
    except Exception as exc:
        if token is not None:
            _log_failed(document.document_id, exc, started)
        raise SystemExit(f"Não consegui cortar o documento {document.document_id}.") from exc
    else:
        log_event(
            "ingest.document.chunked",
            logger_name=__name__,
            context=TraceContext(
                document_id=document.document_id,
                chunks=len(chunks),
                latency_ms=elapsed_ms(started),
            ),
        )
        return chunks
    finally:
        release_trace(token)


def _chunk(document: ExtractedDocument) -> tuple[Chunk, ...]:
    profile = _DOCUMENTS.get(document.document_id)
    if profile is None:
        raise SystemExit(
            f"Documento {document.document_id} sem perfil de ingestão. "
            "Registre os metadados dele em eletric_motor/rag/chunk.py."
        )
    chunks: list[Chunk] = []
    language = profile.language
    for section in document.sections:
        if profile.detect_language:
            language = _language_of(section.markdown, fallback=language)
        chunks.extend(_section_chunks(document, section, profile, language))
    if not chunks:
        raise SystemExit(f"O documento {document.document_id} não gerou nenhum chunk.")
    return tuple(chunks)


def _language_of(text: str, fallback: str) -> str:
    try:
        code = detect(text[:_LANGUAGE_SAMPLE])
    except LangDetectException:
        return fallback
    return _LANGUAGE_MAP.get(code, fallback)


def _section_chunks(
    document: ExtractedDocument,
    section: DocumentSection,
    profile: DocumentProfile,
    language: str,
) -> list[Chunk]:
    title = section.section_path[-1]
    chunks: list[Chunk] = []
    for kind, block in _split_blocks(section.markdown):
        if kind == "table":
            pieces = [f"{title}\n\n{block}"]
        else:
            if not _has_prose(block, title):
                continue
            pieces = _split_prose(block)
        chunks.extend(
            _make_chunk(document, section, profile, language, kind, piece) for piece in pieces
        )
    return chunks


def _split_blocks(markdown: str) -> list[tuple[Literal["prose", "table"], str]]:
    paragraphs = [p.strip() for p in markdown.split("\n\n") if p.strip()]
    blocks: list[list[str]] = []
    for paragraph in paragraphs:
        if _is_table_rows(paragraph):
            caption = ""
            if blocks and blocks[-1][0] == "prose":
                # A legenda exportada com a tabela é o último parágrafo da prosa.
                head, sep, tail = blocks[-1][1].rpartition("\n\n")
                if _is_table_caption(tail):
                    caption = tail
                    if sep:
                        blocks[-1][1] = head
                    else:
                        blocks.pop()
            blocks.append(["table", f"{caption}\n\n{paragraph}" if caption else paragraph])
            continue
        if blocks and blocks[-1][0] == "table":
            # O Docling repete a legenda da tabela como item caption logo após ela.
            if paragraph == blocks[-1][1].split("\n\n", 1)[0]:
                continue
        if blocks and blocks[-1][0] == "prose":
            blocks[-1][1] += "\n\n" + paragraph
        else:
            blocks.append(["prose", paragraph])
    return [(kind, text) for kind, text in blocks]


def _is_table_rows(paragraph: str) -> bool:
    return any(line.startswith("|") for line in paragraph.splitlines())


def _is_table_caption(paragraph: str) -> bool:
    return "\n" not in paragraph and paragraph.casefold().startswith("tabela")


def _has_prose(block: str, title: str) -> bool:
    lines = block.splitlines()
    body = "\n".join(lines[1:]) if lines[0].startswith("#") else block
    return _PROSE_WORD.search(body) is not None


def _split_prose(text: str) -> list[str]:
    if _count_tokens(text) <= _PROSE_CHUNK_SIZE:
        return [text]
    return [piece.strip() for piece in _splitter().split_text(text) if piece.strip()]


def _make_chunk(
    document: ExtractedDocument,
    section: DocumentSection,
    profile: DocumentProfile,
    language: str,
    kind: Literal["prose", "table"],
    content: str,
) -> Chunk:
    return Chunk(
        document_id=document.document_id,
        document_title=document.document_title,
        section_path=section.section_path,
        page=section.page,
        kind=kind,
        content=content,
        content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        tokens=_count_tokens(content),
        source_type=profile.source_type,
        manufacturer=profile.manufacturer,
        language=language,
        topic=_topic_for(section.section_path),
        norm_code=profile.norm_code,
    )


def _topic_for(section_path: tuple[str, ...]) -> Topic | None:
    text = " ".join(section_path).casefold()
    for topic, keywords in _TOPIC_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return topic
    return None


@cache
def _encoder() -> tiktoken.Encoding:
    return tiktoken.get_encoding("cl100k_base")


@cache
def _splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=_PROSE_CHUNK_SIZE,
        chunk_overlap=_PROSE_CHUNK_OVERLAP,
    )


def _count_tokens(text: str) -> int:
    return len(_encoder().encode(text))


def _log_failed(document_id: str, exc: BaseException, started: float) -> None:
    origin = error_origin(exc)
    log_event(
        "ingest.document.failed",
        level="error",
        logger_name=__name__,
        context=TraceContext(
            document_id=document_id,
            latency_ms=elapsed_ms(started),
            error_type=type(exc).__name__,
            error_message=error_message(exc),
            error_file=None if origin is None else origin[0],
            error_line=None if origin is None else origin[1],
            error_function=None if origin is None else origin[2],
        ),
    )
