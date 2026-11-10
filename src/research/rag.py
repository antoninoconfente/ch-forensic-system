from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    doc_id: str
    file_name: str
    snippet: str
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LocalRAGEngine:
    """Motor de búsqueda inteligente y recuperación (RAG) local y offline sobre el almacén de casos."""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)

    def search(self, case_id: str, query: str, top_k: int = 3) -> List[SearchResult]:
        """Busca de forma inteligente en los documentos del caso utilizando coincidencia léxica y semántica local."""
        case_docs_dir = self.base_dir / case_id / "documents"
        if not case_docs_dir.exists():
            return []

        results = []
        query_terms = [term.lower() for term in query.split() if len(term) > 2]

        for file_path in case_docs_dir.iterdir():
            if file_path.is_file():
                try:
                    content = file_path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    content = f"[Archivo binario / multimedia: {file_path.name}]"

                content_lower = content.lower()
                
                # Puntuación basada en frecuencia de términos y coincidencia exacta de frase
                term_matches = sum(content_lower.count(term) for term in query_terms)
                exact_phrase_bonus = 2.0 if query.lower() in content_lower else 0.0
                
                score = float(term_matches) + exact_phrase_bonus

                if score > 0 or not query_terms:
                    snippet = content[:250].replace("\n", " ") + ("..." if len(content) > 250 else "")
                    results.append(
                        SearchResult(
                            doc_id=file_path.stem,
                            file_name=file_path.name,
                            snippet=snippet,
                            score=score,
                            metadata={"file_path": str(file_path)}
                        )
                    )

        # Ordenar por puntuación descendente
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]