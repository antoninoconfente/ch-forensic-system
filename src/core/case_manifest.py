from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CaseEvidenceItem(BaseModel):
    evidence_id: str
    file_path: str
    sha256: str
    file_size_bytes: int
    added_at: str


class CaseManifest(BaseModel):
    case_id: str
    title: str
    description: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    evidences: List[CaseEvidenceItem] = []
    observations: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}

    def save_to_disk(self, base_dir: str = "data/cases") -> Path:
        """Guarda el manifiesto del caso en un archivo JSON estructurado de forma inmutable/limpia."""
        cases_dir = Path(base_dir)
        cases_dir.mkdir(parents=True, exist_ok=True)
        
        manifest_path = cases_dir / f"{self.case_id}.json"
        
        # Guardado ordenado y legible para humanos
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))
            
        return manifest_path

    @classmethod
    def load_from_disk(cls, case_id: str, base_dir: str = "data/cases") -> "CaseManifest":
        """Carga un manifiesto de caso existente desde el disco."""
        manifest_path = Path(base_dir) / f"{case_id}.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"El caso '{case_id}' no existe en el directorio de casos.")
            
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        return cls(**data)