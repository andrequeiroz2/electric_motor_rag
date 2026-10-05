import argparse
import os
import sys
import traceback
from pathlib import Path

from eletric_motor.rag.collection import init_collection
from eletric_motor.rag.ingest import ingest_document
from eletric_motor.rag.search import SearchFilters, search_chunks


def main() -> None:
    parser = argparse.ArgumentParser(prog="eletric-motor")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-collection", help="Cria a coleção híbrida motores no Qdrant")
    ingest = sub.add_parser("ingest", help="Extrai um PDF e corta em chunks com metadados")
    ingest.add_argument("path", type=Path, help="Caminho do PDF a ingerir")
    query = sub.add_parser("query", help="Busca híbrida na coleção e lista os trechos")
    query.add_argument("question", help="Pergunta em linguagem natural")
    query.add_argument("--limit", type=int, default=8, help="Quantos trechos retornar (padrão 8)")
    query.add_argument("--source-type", help="Filtra por tipo de fonte (manual, norma, guia)")
    query.add_argument("--manufacturer", help="Filtra por fabricante (ex.: weg)")
    query.add_argument("--topic", help="Filtra por tópico (ex.: partida)")
    query.add_argument("--norm-code", help="Filtra por código de norma (ex.: 5410)")
    query.add_argument("--language", help="Filtra por idioma (ex.: pt-BR)")
    args = parser.parse_args()
    if args.command == "init-collection":
        status = init_collection()
        action = "criada" if status.created else "já existia"
        indexes = ", ".join(status.indexes_added) if status.indexes_added else "nenhum novo"
        print(f"Coleção {status.name} {action}. Índices adicionados: {indexes}.")
    elif args.command == "ingest":
        result = ingest_document(args.path)
        document = result.document
        prose = sum(1 for chunk in result.chunks if chunk.kind == "prose")
        tables = len(result.chunks) - prose
        print(
            f"Documento {document.document_id}: {document.pages} páginas, "
            f"{len(document.sections)} seções, {len(result.chunks)} chunks "
            f"({prose} de prosa, {tables} de tabelas). "
            f"Pontos: {result.store.points_written} gravados, "
            f"{result.store.points_updated} atualizados, "
            f"{result.store.points_existing} já existiam."
        )
    elif args.command == "query":
        filters = SearchFilters(
            source_type=args.source_type,
            manufacturer=args.manufacturer,
            topic=args.topic,
            norm_code=args.norm_code,
            language=args.language,
        )
        result = search_chunks(args.question, filters, limit=args.limit)
        print(f"{len(result.hits)} trechos para: {args.question}")
        for rank, hit in enumerate(result.hits, start=1):
            chunk = hit.chunk
            section = " › ".join(chunk.section_path)
            kind = "prosa" if chunk.kind == "prose" else "tabela"
            print(
                f"\n[{rank}] {chunk.document_title} — p.{chunk.page} — "
                f"{kind} — score {hit.score:.3f}"
            )
            print(f"    {section}")
            snippet = " ".join(chunk.content.split())[:200]
            print(f"    {snippet}...")


def cli() -> None:
    """Console entrypoint that forces process exit.

    Native threads from onnxruntime/Docling occasionally block the
    interpreter shutdown, so we flush and exit explicitly.
    """
    status = 0
    try:
        main()
    except SystemExit as exc:
        if exc.code is None:
            status = 0
        elif isinstance(exc.code, int):
            status = exc.code
        else:
            print(exc.code, file=sys.stderr)
            status = 1
    except BaseException:
        traceback.print_exc()
        status = 1
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(status)
