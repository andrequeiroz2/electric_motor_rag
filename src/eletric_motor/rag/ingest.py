import re
import time
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
from docling.document_converter import DocumentConverter, PdfFormatOption
from pydantic import BaseModel, ConfigDict, Field

from eletric_motor.rag.chunk import Chunk, chunk_document
from eletric_motor.rag.store import StoreResult, store_chunks
from eletric_motor.rag.trace import (
    TraceContext,
    bind_trace,
    elapsed_ms,
    error_message,
    error_origin,
    log_event,
    release_trace,
    trace_scope,
)

# O Docling não separa nível de título; a hierarquia vem da numeração (1.2.3).
_MAX_SECTION_DEPTH = 4
_SKIP_LABELS = {"picture", "document_index", "footnote"}
_BULLET_PREFIXES = ("- ", "* ", "口")
# Numeração no início do título: "1 T", "1. T", "1.2 T" e "1.Texto" (catálogo W22).
_SECTION_NUMBER = re.compile(r"^(\d+(?:\.\d+)*)\.?(?:\s|[\x00-\x1f]|$|(?=[A-ZÀ-Ö]))")
_CONTROL_CHARS = re.compile(r"[\x00-\x1f]+")
# Títulos numerados que não são seções: caixas de referência cruzada do manual.
_FALSE_HEADERS: dict[str, tuple[str, ...]] = {
    "weg-manual-geral-iom-50033244": (
        "8. recomendações adicionais:",
        "8. recomendaciones adicionales:",
    ),
}
# Cabeçalho repetido no alto das páginas; não é seção do documento.
_PAGE_HEADERS: dict[str, tuple[str, ...]] = {
    "weg-guia-especificacao-50032749": ("acessórios opcionais",),
}
# Títulos de capa e índice, sem numeração, que abrem cada documento.
_TOP_LEVELS: dict[str, tuple[str, ...]] = {
    "weg-guia-especificacao-50032749": (
        "índice",
        "guia de especificação",
        "especificação de motores elétricos",
    ),
    "weg-manual-geral-iom-50033244": (
        "electric motors",
        "eletric motors",
        "motores elétricos",
        "motores eléctricos",
        "installation, operation and maintenance manual",
        "manual general de instalación",
        "manual geral de instalação",
    ),
    "weg-w22-catalogo-50025536": (
        "linha w22",
        "índice",
        "eficiência e confiabilidade",
        "lei de eficiência energética",
    ),
    "NBR-5410": (
        "norma brasileira",
        "abnt nbr",
        "5410",
        "instalações elétricas de baixa tensão",
        "electrical installations of buildings",
        "índice",
        "sumário",
        "prefácio",
    ),
}


class DocumentSection(BaseModel, frozen=True):
    model_config = ConfigDict(extra="forbid")

    section_path: tuple[str, ...] = Field(min_length=1)
    page: int = Field(ge=1)
    markdown: str = Field(min_length=1)


class ExtractedDocument(BaseModel, frozen=True):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    document_title: str = Field(min_length=1)
    pages: int = Field(ge=1)
    sections: tuple[DocumentSection, ...] = Field(min_length=1)


class IngestResult(BaseModel, frozen=True):
    model_config = ConfigDict(extra="forbid")

    document: ExtractedDocument
    chunks: tuple[Chunk, ...]
    store: StoreResult


def ingest_document(path: Path) -> IngestResult:
    with trace_scope():
        started = time.perf_counter()
        document_id = path.stem
        _log_started(document_id)
        try:
            document = extract_document(path)
            chunks = chunk_document(document)
            store = store_chunks(chunks)
        except SystemExit as exc:
            _log_failed(document_id, exc.__cause__ or exc, started)
            raise
        except Exception as exc:
            _log_failed(document_id, exc, started)
            raise SystemExit(f"Não consegui ingerir o PDF {path}.") from exc
        log_event(
            "ingest.document.completed",
            logger_name=__name__,
            context=TraceContext(
                document_id=document_id,
                pages=document.pages,
                sections=len(document.sections),
                chunks=len(chunks),
                points_written=store.points_written,
                points_existing=store.points_existing,
                points_updated=store.points_updated,
                latency_ms=elapsed_ms(started),
            ),
        )
        return IngestResult(document=document, chunks=chunks, store=store)


def extract_document(path: Path) -> ExtractedDocument:
    token = bind_trace()
    started = time.perf_counter()
    document_id = path.stem
    if token is not None:
        _log_started(document_id)
    try:
        extracted = _extract(path)
    except Exception as exc:
        if token is not None:
            _log_failed(document_id, exc, started)
        raise SystemExit(f"Não consegui extrair o PDF {path}.") from exc
    else:
        log_event(
            "ingest.document.extracted",
            logger_name=__name__,
            context=TraceContext(
                document_id=document_id,
                pages=extracted.pages,
                sections=len(extracted.sections),
                latency_ms=elapsed_ms(started),
            ),
        )
        return extracted
    finally:
        release_trace(token)


def _log_started(document_id: str) -> None:
    log_event(
        "ingest.document.started",
        logger_name=__name__,
        context=TraceContext(document_id=document_id),
    )


def _extract(path: Path) -> ExtractedDocument:
    if not path.is_file():
        raise FileNotFoundError(path)
    result = _converter().convert(str(path))
    doc = result.document
    pages = len(doc.pages)
    if pages == 0:
        raise ValueError("nenhuma página extraída")

    sections: list[DocumentSection] = []
    heading_stack: list[str] = []
    current_path: tuple[str, ...] = (path.stem,)
    current_page = 1
    buffer: list[str] = []
    page_headers = _PAGE_HEADERS.get(path.stem, ())
    top_levels = _TOP_LEVELS.get(path.stem, ())
    false_headers = _FALSE_HEADERS.get(path.stem, ())

    def flush() -> None:
        markdown = "\n\n".join(buffer).strip()
        buffer.clear()
        if markdown:
            sections.append(
                DocumentSection(
                    section_path=current_path,
                    page=current_page,
                    markdown=markdown,
                )
            )

    for item, _level in doc.iterate_items():
        label = str(getattr(item, "label", ""))
        if label in _SKIP_LABELS:
            continue
        prov = getattr(item, "prov", None)
        page = prov[0].page_no if prov else current_page
        if label == "section_header":
            title = _CONTROL_CHARS.sub(" ", item.text).strip()
            if _is_page_noise(title, page_headers, top_levels, false_headers):
                continue
            flush()
            depth = _section_depth(title)
            del heading_stack[depth - 1 :]
            heading_stack.append(title)
            current_path = tuple(heading_stack)
            current_page = page
            buffer.append("#" * min(depth, 6) + " " + title)
            continue
        markdown = _item_markdown(item, label, doc)
        if not markdown:
            continue
        if not buffer:
            current_page = page
        buffer.append(markdown)
    flush()

    if not sections:
        raise ValueError("nenhum trecho de texto extraído")
    return ExtractedDocument(
        document_id=path.stem,
        document_title=sections[0].section_path[-1],
        pages=pages,
        sections=tuple(sections),
    )


# O modo accurate do TableFormer mutilou grades grandes (924 de 926 células da
# Tabela 1.2 do guia descartadas, sobrou 2x2); o modo fast extraiu a grade 46x31.
def _converter() -> DocumentConverter:
    options = PdfPipelineOptions()
    options.table_structure_options.mode = TableFormerMode.FAST
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )


def _is_page_noise(
    title: str,
    page_headers: tuple[str, ...],
    top_levels: tuple[str, ...],
    false_headers: tuple[str, ...],
) -> bool:
    lowered = title.casefold()
    if lowered in page_headers or lowered in false_headers:
        return True
    if _SECTION_NUMBER.match(title):
        return False
    if lowered.startswith(top_levels):
        return False
    return True


def _section_depth(title: str) -> int:
    match = _SECTION_NUMBER.match(title)
    if match is None:
        return 1
    return min(match.group(1).count(".") + 1, _MAX_SECTION_DEPTH)


def _item_markdown(item: object, label: str, doc: object) -> str:
    if label == "table":
        return item.export_to_markdown(doc=doc).strip()
    text = (getattr(item, "text", "") or "").strip()
    if not text:
        return ""
    if label == "list_item" and not text.startswith(_BULLET_PREFIXES):
        return "- " + text
    return text


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
