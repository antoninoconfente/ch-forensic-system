import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Optional

class EvidenceManager:
    def __init__(self, base_storage_path: str = "data/missions"):
        self.base_path = Path(base_storage_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _calculate_sha256(self, file_path: Path) -> str:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def create_mission_folder(
        self, 
        mission_id: str, 
        description: str, 
        image_paths: Optional[List[str]] = None
    ) -> dict:
        """
        Crea un expediente único con metadata y copias inmutables de múltiples imágenes.
        """
        mission_dir = self.base_path / mission_id
        mission_dir.mkdir(parents=True, exist_ok=True)
        
        saved_images = []

        if image_paths:
            for img_path in image_paths:
                src_path = Path(img_path)
                if src_path.exists():
                    img_hash = self._calculate_sha256(src_path)
                    dst_path = mission_dir / src_path.name
                    
                    # Copia inmutable
                    with open(src_path, "rb") as src, open(dst_path, "wb") as dst:
                        dst.write(src.read())
                    
                    saved_images.append({
                        "filename": src_path.name,
                        "sha256": img_hash,
                        "size_bytes": src_path.stat().st_size
                    })
                
        metadata = {
            "mission_id": mission_id,
            "created_at": datetime.now().isoformat(),
            "description": description,
            "images": saved_images,
            "total_images": len(saved_images),
            "status": "initialized"
        }

        meta_file = mission_dir / "metadata.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4, ensure_ascii=False)

        return metadata