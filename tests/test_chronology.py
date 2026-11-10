from pathlib import Path
import pytest
from src.research.chronology import ChronologyStore, TimelineEvent


def test_add_and_sort_chronology_events(tmp_path: Path) -> None:
    store = ChronologyStore(tmp_path)
    case_id = "test-case-chrono"

    # Añadir un evento posterior primero para probar la ordenación
    store.add_event(
        case_id=case_id,
        event_id="evt-02",
        timestamp="2026-03-01T10:00:00Z",
        title="Segundo Hito",
        description="Descripción del segundo acontecimiento.",
        actors=["Investigador B"],
        evidence_refs=["ev-01"],
    )

    # Añadir un evento anterior después
    store.add_event(
        case_id=case_id,
        event_id="evt-01",
        timestamp="2026-01-15T08:30:00Z",
        title="Primer Hito",
        description="Descripción del primer acontecimiento.",
        actors=["Investigador A"],
        document_refs=["ref-01"],
    )

    events = store.list_events(case_id)

    assert len(events) == 2
    # El ordenamiento debe colocar el evento más antiguo primero (evt-01)
    assert events[0].event_id == "evt-01"
    assert events[1].event_id == "evt-02"
    assert events[0].timestamp == "2026-01-15T08:30:00Z"
    assert events[0].actors == ["Investigador A"]
    assert "ref-01" in events[0].document_refs