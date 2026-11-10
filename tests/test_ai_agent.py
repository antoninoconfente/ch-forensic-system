import pytest
from src.research.ai_agent import LocalHermesExplorer

def test_hermes_local_connection():
    # Inicializamos el cliente apuntando al servidor local de la app
    explorer = LocalHermesExplorer(
        base_url="http://localhost:1234/v1",
        model_name="deepseek-v4.1-flash"  # o el nombre del modelo que hayas elegido en la app
    )
    
    assert explorer.client is not None
    assert explorer.model_name == "deepseek-v4.1-flash"
    
    # Prueba de integración corta
    respuesta = explorer.analyze_evidence(
        object_description="Objeto de prueba: Moneda antigua de plata.",
        context_notes="Prueba de conexión corta."
    )
    
    assert len(respuesta) > 0