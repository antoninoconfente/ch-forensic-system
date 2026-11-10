import pytest
from pathlib import Path
from src.core.case_manifest import CaseManifest, CaseEvidenceItem


def test_case_manifest_creation_and_persistence(tmp_path):
    # 1. Crear un manifiesto de prueba
    case = CaseManifest(
        case_id="case-test-01",
        title="Caso de Prueba Arqueológica",
        description="Verificación de lectura y escritura de manifiesto."
    )

    # 2. Añadir una evidencia simulada
    evidence = CaseEvidenceItem(
        evidence_id="ev-01",
        file_path="data/evidence/sample.jpg",
        sha256="2590feaf7c0273803189985ef438a25df913a3a452fa626b4905a42071f0bd0a",
        file_size_bytes=1024,
        added_at="2026-10-30T14:00:00Z"
    )
    case.evidences.append(evidence)

    # 3. Guardar en un directorio temporal
    saved_path = case.save_to_disk(base_dir=str(tmp_path))
    assert saved_path.exists()

    # 4. Cargar desde el disco y verificar la integridad
    loaded_case = CaseManifest.load_from_disk(case_id="case-test-01", base_dir=str(tmp_path))
    assert loaded_case.case_id == "case-test-01"
    assert loaded_case.title == "Caso de Prueba Arqueológica"
    assert len(loaded_case.evidences) == 1
    assert loaded_case.evidences[0].sha256 == "2590feaf7c0273803189985ef438a25df913a3a452fa626b4905a42071f0bd0a"