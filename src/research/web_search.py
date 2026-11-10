import os
import time
from duckduckgo_search import DDGS

class WebSearchEngine:
    @staticmethod
    def search_catalog(query: str, max_results: int = 3) -> list:
        """
        Realiza una búsqueda web robusta utilizando duckduckgo_search para contrastar
        cuños, marcas, modelos y referencias de coleccionismo con reintentos.
        """
        results = []
        for attempt in range(2):
            try:
                with DDGS() as ddgs:
                    for r in ddgs.text(query, max_results=max_results):
                        results.append({
                            "title": r.get("title", "Sin título"),
                            "href": r.get("href", "#"),
                            "body": r.get("body", "Sin descripción")
                        })
                if results:
                    break
            except Exception as e:
                print(f"Intento {attempt+1} fallido en búsqueda web: {e}")
                time.sleep(1)
        return results

    @staticmethod
    def format_search_results_for_prompt(results: list) -> str:
        if not results:
            return "[No se encontraron referencias web externas directas en este momento]"
        
        formatted = "REFERENCIAS Y CATÁLOGOS ENCONTRADOS EN LA WEB:\n"
        for idx, res in enumerate(results, 1):
            formatted += f"{idx}. [{res['title']}]({res['href']})\n   Resumen: {res['body']}\n\n"
        return formatted