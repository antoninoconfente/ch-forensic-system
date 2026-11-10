import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class ObjectMissionRecord(BaseModel):
    object_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sha256_hash: str
    original_filename: str
    file_size_bytes: int
    status: str = Field(default="RAW_INGESTED")  # Estados: RAW_INGESTED, ANALYZED, UNKNOWN
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ObjectMissionStore:
    """Gestiona los expedientes (Misiones) físicos y digitales de cada objeto en disco local."""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_mission(self, object_id: str, file_path: Path, metadata: Optional[Dict[str, Any]] = None) -> ObjectMissionRecord:
        """Crea un expediente único para el objeto, calcula su huella inmutable y guarda los archivos."""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"El archivo de evidencia {file_path} no existe.")

        # Directorio específico para este objeto (su misión)
        mission_dir = self.base_dir / object_id
        docs_dir = mission_dir / "documents"
        docs_dir.mkdir(parents=True, exist_ok=True)

        # Destino final de la evidencia en el expediente
        dest_path = docs_dir / file_path.name

        # Cálculo de SHA-256 inmutable
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                sha256_hash.update(chunk)
        file_hash = sha256_hash.hexdigest()

        # Copiar archivo al expediente si no está ya ahí
        if file_path.resolve() != dest_path.resolve():
            dest_path.write_bytes(file_path.read_bytes())

        record = ObjectMissionRecord(
            object_id=object_id,
            sha256_hash=file_hash,
            original_filename=file_path.name,
            file_size_bytes=file_path.stat().st_size,
            metadata=metadata or {}
        )

        # Guardar manifiesto JSON del expediente usando model_dump_json
        manifest_path = mission_dir / "manifest.json"
        manifest_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")

        return record