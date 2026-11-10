import os
import json
import hashlib
from datetime import datetime

class MissionManager:
    def __init__(self, data_dir="data/missions"):
        self.data_dir = data_dir
        self.registry_path = os.path.join(data_dir, "missions_registry.json")
        os.makedirs(self.data_dir, exist_ok=True)
        self._init_registry()

    def _init_registry(self):
        if not os.path.exists(self.registry_path):
            with open(self.registry_path, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=4)

    def load_registry(self) -> dict:
        if os.path.exists(self.registry_path):
            with open(self.registry_path, "r", encoding="utf-8") as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {}
        return {}

    def save_mission_state(self, mission_id: str, description: str, notes: str, report: str, image_paths: list):
        mission_dir = os.path.join(self.data_dir, mission_id)
        os.makedirs(mission_dir, exist_ok=True)

        # Calcular hash SHA-256 del informe para inmutabilidad forense
        report_bytes = report.encode("utf-8")
        report_hash = hashlib.sha256(report_bytes).hexdigest()

        registry = self.load_registry()
        
        # Actualizar o crear registro
        registry[mission_id] = {
            "mission_id": mission_id,
            "timestamp": datetime.now().isoformat(),
            "description": description,
            "notes": notes,
            "images": image_paths,
            "report_hash": report_hash,
            "updates_count": registry.get(mission_id, {}).get("updates_count", 0) + 1
        }

        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=4)

        # Guardar el informe con su huella en la carpeta del caso
        report_path = os.path.join(mission_dir, "analysis_report.md")
        with open(report_path, "w", encoding="utf-8") as rf:
            rf.write(f"# Expediente Forense: {mission_id}\n")
            rf.write(f"**Hash de Integridad (SHA-256):** `{report_hash}`\n\n")
            rf.write(report)

        return report_hash

    def verify_mission_integrity(self, mission_id: str) -> dict:
        """
        Verifica si el informe pericial en disco coincide con el hash SHA-256 
        registrado originalmente, detectando cualquier manipulación externa.
        """
        registry = self.load_registry()
        if mission_id not in registry:
            return {"status": "error", "message": "Expediente no encontrado en el registro."}
        
        stored_hash = registry[mission_id].get("report_hash")
        mission_dir = os.path.join(self.data_dir, mission_id)
        report_path = os.path.join(mission_dir, "analysis_report.md")
        
        if not os.path.exists(report_path):
            return {"status": "compromised", "message": "El archivo de informe físico no existe en disco."}
            
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            # Excluimos las primeras 2 líneas (título y cabecera de hash) para recalcular 
            # exactamente el hash del contenido pericial puro.
            raw_content = "".join(lines[2:]) if len(lines) > 2 else "".join(lines)
            current_hash = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()
            
            if current_hash == stored_hash:
                return {
                    "status": "valid", 
                    "message": "Integridad verificada con éxito. El expediente no ha sido alterado.", 
                    "hash": current_hash
                }
            else:
                return {
                    "status": "tampered", 
                    "message": "¡ALERTA FORENSE! El informe ha sido modificado externamente (brecha en la cadena de custodia).", 
                    "stored": stored_hash, 
                    "current": current_hash
                }
        except Exception as e:
            return {"status": "error", "message": str(e)}