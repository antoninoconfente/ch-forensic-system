from pathlib import Path
from src.research.cli import main


def test_cli_ingest_document(tmp_path: Path) -> None:
    argv = [
        "ingest-doc",
        "--base-dir",
        str(tmp_path),
        "--case-id",
        "cli-case",
        "--doc-id",
        "doc-cli-01",
        "--content",
        "Contenido de prueba vía CLI.",
    ]
    exit_code = main(argv)
    assert exit_code == 0
    assert (tmp_path / "cli-case" / "documents" / "doc-cli-01.md").exists()


def test_cli_add_event(tmp_path: Path) -> None:
    argv = [
        "add-event",
        "--base-dir",
        str(tmp_path),
        "--case-id",
        "cli-case",
        "--event-id",
        "evt-cli-01",
        "--timestamp",
        "2026-06-01T12:00:00Z",
        "--title",
        "Hito CLI",
        "--description",
        "Descripción del hito de prueba.",
    ]
    exit_code = main(argv)
    assert exit_code == 0
    assert (tmp_path / "cli-case" / "chronology" / "evt-cli-01.json").exists()