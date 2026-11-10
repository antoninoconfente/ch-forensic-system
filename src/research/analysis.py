from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ResearchFinding(BaseModel):
    finding_id: str
    title: str
    description: str
    confidence_level: str  # e.g., "high", "medium", "low"
    linked_evidence_refs: List[str] = Field(default_factory=list)
    linked_document_refs: List[str] = Field(default_factory=list)
    linked_event_refs: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    recorded_at: str


class AnalysisStore:
    """Gestor para el análisis y síntesis de hipótesis y hallazgos de la investigación."""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def record_finding(
        self,
        case_id: str,
        finding_id: str,
        title: str,
        description: str,
        confidence_level: str = "medium",
        linked_evidence_refs: Optional[List[str]] = None,
        linked_document_refs: Optional[List[str]] = None,
        linked_event_refs: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ResearchFinding:
        """Registra un hallazgo o conclusión analítica vinculada a fuentes y eventos."""
        case_dir = self.base_dir / case_id / "analysis"
        case_dir.mkdir(parents=True, exist_ok=True)

        finding_path = case_dir / f"{finding_id}.json"

        finding = ResearchFinding(
            finding_id=finding_id,
            title=title,
            description=description,
            confidence_level=confidence_level,
            linked_evidence_refs=linked_evidence_refs or [],
            linked_document_refs=linked_document_refs or [],
            linked_event_refs=linked_event_refs or [],
            metadata=metadata or {},
            recorded_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )

        finding_path.write_text(finding.model_dump_json(indent=2), encoding="utf-8")
        return finding

    def list_findings(self, case_id: str) -> List[ResearchFinding]:
        """Lista todos los hallazgos analíticos registrados para un caso."""
        case_dir = self.base_dir / case_id / "analysis"
        if not case_dir.exists():
            return []

        findings = []
        for file_path in case_dir.glob("*.json"):
            data = json.loads(file_path.read_text(encoding="utf-8"))
            findings.append(ResearchFinding(**data))

        findings.sort(key=lambda f: f.recorded_at)
        return findings