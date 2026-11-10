from pathlib import Path
from typing import List, Optional
from src.research.evidence import EvidenceManager
from src.research.ai_agent import LocalAIAgent

class VerticalSlicePipeline:
    def __init__(self, storage_path: str = "data/missions"):
        self.evidence_manager = EvidenceManager(base_storage_path=storage_path)
        self.ai_agent = LocalAIAgent()

    def execute_mission(
        self, 
        mission_id: str, 
        description: str, 
        image_paths: Optional[List[str]] = None, 
        context_notes: str = ""
    ) -> dict:
        """
        Ejecuta el corte vertical completo: 
        1. Ingesta segura y multi-imagen de evidencias.
        2. Análisis forense local mediante IA.
        3. Generación de informe en Markdown.
        """
        print(f"\n--- [Fase A] Iniciando expediente para la misión: {mission_id} ---")
        
        # 1. Crear expediente y guardar copias inmutables de las imágenes
        metadata = self.evidence_manager.create_mission_folder(
            mission_id=mission_id,
            description=description,
            image_paths=image_paths
        )
        print(f"[✔] Expediente guardado. Total de imágenes: {metadata.get('total_images', 0)}")

        # 2. Análisis con el Agente Local
        print(f"--- [Fase B] Consultando al Analista Local (Hermes) ---")
        prompt_content = f"Descripción del objeto: {description}\nNotas de contexto: {context_notes}\nMetadatos de evidencias: {metadata}"
        analysis_result = self.ai_agent.analyze(prompt_content)
        print(f"[✔] Análisis completado con éxito.")

        # 3. Generación del informe final en Markdown
        mission_dir = Path(self.evidence_manager.base_path) / mission_id
        report_path = mission_dir / "analysis_report.md"
        
        report_content = f"""# Ficha de Investigación Forense - {mission_id}
## Metadatos del Expediente
- **ID de Misión:** {metadata['mission_id']}
- **Fecha de Creación:** {metadata['created_at']}
- **Total de Evidencias Visuales:** {metadata.get('total_images', 0)}
- **Descripción Inicial:** {description}

## Análisis del Agente Local (Hermes)
{analysis_result}
"""
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)
            
        print(f"--- [✔] Criterio completado: Ficha generada en {report_path} ---\n")

        return {
            "metadata": metadata,
            "analysis": analysis_result,
            "report_path": str(report_path)
        }