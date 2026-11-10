import os
import requests
import base64
from PIL import Image
import io

# Clave de SerpApi de respaldo detectada en el sistema
DEFAULT_SERPAPI_KEY = "2ffcce2d3653f2aa7c1023426d27f70cc78650c159fc3dbb0e4a6ae52e979323"

class VisualSearchEngine:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("SERPAPI_KEY") or DEFAULT_SERPAPI_KEY

    def search_by_image_path(self, image_path: str, max_results: int = 5) -> dict:
        """
        Búsqueda inversa visual mediante Google Lens Engine en SerpApi enviando el archivo local.
        Devuelve dict con {'status': 'SUCCESS'|'ERROR', 'code': '...', 'results': [...]}
        """
        if not self.api_key:
            return {
                "status": "ERROR",
                "code": "[ERR_L2_SERPAPI_MISSING_KEY]",
                "message": "No se encontró la clave de SERPAPI_KEY.",
                "results": []
            }

        if not os.path.exists(image_path):
            return {
                "status": "ERROR",
                "code": "[ERR_L1_FILE_NOT_FOUND]",
                "message": f"El archivo de imagen no existe en la ruta: {image_path}",
                "results": []
            }

        endpoint = "https://serpapi.com/search"
        
        # Parámetros para Google Lens con SerpApi
        params = {
            "engine": "google_lens",
            "api_key": self.api_key
        }
        
        try:
            # Enviamos la imagen local directamente mediante multipart/form-data
            with open(image_path, "rb") as img_file:
                files = {"file": img_file}
                print(f"📸 [VISUAL SEARCH] Enviando imagen local a Google Lens (SerpApi): {image_path}")
                response = requests.post(endpoint, params=params, files=files, timeout=15)
            
            if response.status_code == 401 or response.status_code == 403:
                return {
                    "status": "ERROR",
                    "code": "[ERR_L2_SERPAPI_UNAUTHORIZED]",
                    "message": f"Acceso denegado en SerpApi (HTTP {response.status_code}). Revise su suscripción/clave.",
                    "results": []
                }
            elif response.status_code != 200:
                return {
                    "status": "ERROR",
                    "code": f"[ERR_L2_SERPAPI_HTTP_{response.status_code}]",
                    "message": f"Respuesta no válida de SerpApi: {response.text[:200]}",
                    "results": []
                }

            data = response.json()
            
            if "error" in data:
                return {
                    "status": "ERROR",
                    "code": "[ERR_L2_SERPAPI_API_ERROR]",
                    "message": str(data.get("error")),
                    "results": []
                }

            matches = data.get("visual_matches", [])[:max_results]
            results = []
            for match in matches:
                results.append({
                    "title": match.get("title", "Coincidencia Visual"),
                    "link": match.get("link", "#"),
                    "source": match.get("source", "Catálogo Web"),
                    "price": match.get("price", {}).get("extracted", "N/A"),
                    "thumbnail": match.get("thumbnail", "")
                })

            return {
                "status": "SUCCESS",
                "code": "[OK_VISUAL_SEARCH]",
                "results": results
            }

        except requests.exceptions.Timeout:
            return {
                "status": "ERROR",
                "code": "[ERR_L3_SERPAPI_TIMEOUT]",
                "message": "Tiempo de espera agotado al conectar con el motor de búsqueda visual.",
                "results": []
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "code": "[ERR_L3_VISUAL_EXCEPTION]",
                "message": str(e),
                "results": []
            }

    def search_by_image_url(self, image_url: str, max_results: int = 5) -> dict:
        """
        Búsqueda inversa visual mediante URL directa.
        """
        if not self.api_key:
            return {
                "status": "ERROR",
                "code": "[ERR_L2_SERPAPI_MISSING_KEY]",
                "results": []
            }

        endpoint = "https://serpapi.com/search"
        params = {
            "engine": "google_lens",
            "url": image_url,
            "api_key": self.api_key
        }
        
        try:
            response = requests.get(endpoint, params=params, timeout=12)
            data = response.json()
            matches = data.get("visual_matches", [])[:max_results]
            results = [
                {
                    "title": m.get("title", "Coincidencia Visual"),
                    "link": m.get("link", "#"),
                    "source": m.get("source", "Catálogo Web"),
                    "price": m.get("price", {}).get("extracted", "N/A"),
                    "thumbnail": m.get("thumbnail", "")
                }
                for m in matches
            ]
            return {"status": "SUCCESS", "code": "[OK_VISUAL_SEARCH]", "results": results}
        except Exception as e:
            return {"status": "ERROR", "code": "[ERR_L3_VISUAL_EXCEPTION]", "message": str(e), "results": []}

    def format_visual_results(self, visual_response: dict) -> str:
        if visual_response.get("status") == "ERROR":
            return f"⚠️ [ADVERTENCIA VISUAL {visual_response.get('code')}]: {visual_response.get('message')}"
            
        results = visual_response.get("results", [])
        if not results:
            return "[No se recuperaron coincidencias visuales directas por imagen en Google Lens]"
            
        formatted = "📸 COINCIDENCIAS VISUALES DIRECTAS (GOOGLE LENS / CATÁLOGOS DE SUBASAS):\n"
        for idx, item in enumerate(results, 1):
            formatted += f"{idx}. [{item['title']}]({item['link']})\n"
            formatted += f"   Fuente: {item['source']} | Valor Ref: {item['price']}\n\n"
        return formatted