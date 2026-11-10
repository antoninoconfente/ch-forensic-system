from pathlib import Path
from src.research.documents import DocumentStore
from src.research.rag import LocalRAGEngine, SearchResult


def test_local_rag_search(tmp_path: Path) -> None:
    case_id = "rag-case-01"
    store = DocumentStore(tmp_path)
    
    # Ingerir documentos de prueba variados
    store.ingest_document(case_id, "doc-01", "El sospechoso fue visto en el puerto de la ciudad a medianoche.")
    store.ingest_document(case_id, "doc-02", "Informe financiero sobre la empresa fantasma vinculada al caso principal.")
    store.ingest_document(case_id, "doc-03", "Testimonio clave: El vehículo del sospechoso era de color rojo oscuro.")

    rag = LocalRAGEngine(tmp_path)
    
    # Realizar consulta específica
    results = rag.search(case_id, "vehículo sospechoso")
    
    assert isinstance(results, list)
    assert len(results) > 0
    
    # El documento 3 debe aparecer primero por coincidir con "vehículo" y "sospechoso"
    top_result = results[0]
    assert isinstance(top_result, SearchResult)
    assert top_result.doc_id == "doc-03"
    assert "vehículo" in top_result.snippet.lower()