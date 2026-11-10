from pathlib import Path
import pytest
from src.research.analysis import AnalysisStore, ResearchFinding


def test_record_and_list_findings(tmp_path: Path) -> None:
    store = AnalysisStore(tmp_path)
    case_id = "test-case-analysis"

    finding = store.record_finding(
        case_id=case_id,
        finding_id="finding-01",
        title="Correlación entre el documento y el evento temporal",
        description="Se observa que el documento de referencia corrobora el hito cronológico.",
        confidence_level="high",
        linked_evidence_refs=["ev-01"],
        linked_document_refs=["ref-history-01"],
        linked_event_refs=["evt-01"],
        metadata={"analyst": "IA Investigador"},
    )

    findings = store.list_findings(case_id)

    assert len(findings) == 1
    assert findings[0].finding_id == "finding-01"
    assert findings[0].confidence_level == "high"
    assert "ref-history-01" in findings[0].linked_document_refs
    assert "evt-01" in findings[0].linked_event_refs
    assert findings[0].recorded_at