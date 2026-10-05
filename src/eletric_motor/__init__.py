import argparse
from pathlib import Path

from eletric_motor.rag.collection import init_collection
from eletric_motor.rag.ingest import ingest_document


def main() -> None:
    parser = argparse.ArgumentParser(prog="eletric-motor")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-collection", help="Cria a coleção híbrida motores no Qdrant")
    ingest = sub.add_parser("ingest", help="Extrai um PDF e corta em chunks com metadados")
    ingest.add_argument("path", type=Path, help="Caminho do PDF a ingerir")
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
            f"{result.store.points_existing} já existiam."
        )
