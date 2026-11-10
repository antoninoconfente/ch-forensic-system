from pathlib import Path
from src.research.documents import ObjectMissionStore, ObjectMissionRecord


def test_object_mission_store(tmp_path: Path) -> None:
    store = ObjectMissionStore(tmp_path)
    
    # Crear un archivo temporal simulando la evidencia de un objeto
    dummy_file = tmp_path / "test_objeto.jpg"
    dummy_file.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100)
    
    object_id = "mision-objeto-001"
    record = store.create_mission(object_id, dummy_file, metadata={"tipo": "fotografia"})
    
    # Verificaciones rigurosas
    assert isinstance(record, ObjectMissionRecord)
    assert record.object_id == object_id
    assert len(record.sha256_hash) == 64 # Longitud estándar SHA-256
    assert record.status == "RAW_INGESTED"
    
    # Comprobar que en disco existe el expediente, el manifiesto JSON y la evidencia
    mission_dir = tmp_path / object_id
    assert mission_dir.exists()
    assert (mission_dir / "manifest.json").exists()
    assert (mission_dir / "documents" / "test_objeto.jpg").exists()