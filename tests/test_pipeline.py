import os
from pathlib import Path
from src.research.pipeline import VerticalSlicePipeline

def test_vertical_slice_multi_image(tmp_path):
    # 1. Creamos un par de imágenes falsas temporales para simular vistas (anverso y reverso)
    img1 = tmp_path / "anverso.jpg"
    img1.write_bytes(b"contenido de prueba para la vista frontal del objeto")
    
    img2 = tmp_path / "reverso.jpg"
    img2.write_bytes(b"contenido de prueba para la vista trasera del objeto")

    # 2. Inicializamos el pipeline
    pipeline = VerticalSlicePipeline(storage_path="data/test_missions")
    
    mission_id = "test_mission_multiview"
    description = "Moneda antigua con múltiples vistas fotográficas (anverso y reverso)."
    context_notes = "Prueba de integración con múltiples evidencias visuales."
    
    # 3. Ejecutamos la misión pasando la lista de imágenes
    result = pipeline.execute_mission(
        mission_id=mission_id,
        description=description,
        image_paths=[str(img1), str(img2)],
        context_notes=context_notes
    )
    
    # 4. Verificaciones estrictas
    assert result["metadata"]["mission_id"] == mission_id
    assert result["metadata"]["total_images"] == 2, "Debe registrar exactamente 2 imágenes."
    assert len(result["metadata"]["images"]) == 2
    assert os.path.exists(result["report_path"]), "El informe markdown debe ser generado."
    
    print(f"\n[✔] ¡Misión multi-imagen procesada e informe generado en: {result['report_path']}!")