from pathlib import Path
import argparse
from src.research.documents import DocumentStore
from src.research.chronology import ChronologyStore
from src.research.analysis import AnalysisStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CLI para el núcleo de investigación ch-core-v2")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Comando para ingerir documentos (Fase 3)
    doc_parser = subparsers.add_parser("ingest-doc", help="Ingesta un documento de referencia")
    doc_parser.add_argument("--base-dir", required=True, type=Path)
    doc_parser.add_argument("--case-id", required=True)
    doc_parser.add_argument("--doc-id", required=True)
    doc_parser.add_argument("--content", required=True)

    # Comando para añadir eventos cronológicos (Fase 4)
    chrono_parser = subparsers.add_parser("add-event", help="Añade un evento a la línea temporal")
    chrono_parser.add_argument("--base-dir", required=True, type=Path)
    chrono_parser.add_argument("--case-id", required=True)
    chrono_parser.add_argument("--event-id", required=True)
    chrono_parser.add_argument("--timestamp", required=True)
    chrono_parser.add_argument("--title", required=True)
    chrono_parser.add_argument("--description", required=True)

    # Comando para registrar hallazgos (Fase 5)
    analysis_parser = subparsers.add_parser("record-finding", help="Registra un hallazgo analítico")
    analysis_parser.add_argument("--base-dir", required=True, type=Path)
    analysis_parser.add_argument("--case-id", required=True)
    analysis_parser.add_argument("--finding-id", required=True)
    analysis_parser.add_argument("--title", required=True)
    analysis_parser.add_argument("--description", required=True)

    args = parser.parse_args(argv)

    if args.command == "ingest-doc":
        store = DocumentStore(args.base_dir)
        ref = store.ingest_document(args.case_id, args.doc_id, args.content)
        print(f"Documento ingerido con éxito: {ref.file_name} (SHA-256: {ref.sha256_hash[:12]}...)")
    elif args.command == "add-event":
        store = ChronologyStore(args.base_dir)
        event = store.add_event(args.case_id, args.event_id, args.timestamp, args.title, args.description)
        print(f"Evento añadido a la línea temporal: {event.event_id} [{event.timestamp}]")
    elif args.command == "record-finding":
        store = AnalysisStore(args.base_dir)
        finding = store.record_finding(args.case_id, args.finding_id, args.title, args.description)
        print(f"Hallazgo analítico registrado: {finding.finding_id} (Nivel: {finding.confidence_level})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())