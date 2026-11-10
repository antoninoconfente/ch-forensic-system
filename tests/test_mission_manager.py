import os
import shutil
from src.research.mission_manager import MissionManager

def test_mission_manager_lifecycle():
    test_dir = "data/test_missions"
    manager = MissionManager(data_dir=test_dir)
    
    mission_id = "test-caso-001"
    description = "Prueba de encendedor antiguo"
    notes = "Verificando integridad y memoria"
    report = "HECHOS: Encendedor BIC.\nHIPÓTESIS: Años 90.\nINCERTIDUMBRES: Ninguna."
    image_paths = ["fake_path_1.jpg"]

    # 1. Guardar estado de misión
    report_hash = manager.save_mission_state(
        mission_id=mission_id,
        description=description,
        notes=notes,
        report=report,
        image_paths=image_paths
    )

    assert report_hash is not None, "El hash SHA-256 no debe ser nulo"
    print(f"\n[OK] Hash generado correctamente: {report_hash}")

    # 2. Cargar registro y verificar persistencia
    registry = manager.load_registry()
    assert mission_id in registry, "El caso debe existir en el registro"
    assert registry[mission_id]["updates_count"] == 1, "El contador de actualizaciones debe ser 1"

    # Limpieza de pruebas
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    print("[OK] Test de MissionManager superado con éxito.")

if __name__ == "__main__":
    test_mission_manager_lifecycle()