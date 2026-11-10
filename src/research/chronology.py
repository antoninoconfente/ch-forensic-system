import os
import base64
from PIL import Image
import io
from openai import OpenAI

class LocalAIAgent:
    def __init__(self, base_url="http://localhost:11434/v1", model_name="llava"):
        self.base_url = base_url
        self.model_name = model_name
        self.client = OpenAI(base_url=self.base_url, api_key="ollama")

    def _optimize_and_encode_image(self, image_path: str, max_size=(512, 512)) -> str:
        """
        Abre la imagen, la redimensiona para aligerar la carga del modelo local
        y la codifica en base64.
        """
        try:
            with Image.open(image_path) as img:
                # Convertir a RGB si es necesario (ej. PNG con transparencia o CMYK)
                img = img.convert("RGB")
                img.thumbnail(max_size)
                
                buffered = io.BytesIO()
                img.save(buffered, format="JPEG", quality=85)
                return base64.b64encode(buffered.getvalue()).decode('utf-8')
        except Exception as e:
            # Si falla la compresión PIL, intentamos leer el raw original
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')

    def analyze(self, object_description: str, context_notes: str = "", image_paths: list = None) -> str:
        return self.analyze_evidence(object_description, context_notes, image_paths)

    def analyze_evidence(self, object_description: str, context_notes: str = "", image_paths: list = None) -> str:
        system_prompt = (
            "Eres un investigador forense y tasador experto. "
            "Analiza las imágenes proporcionadas de forma concisa y directa. "
            "Identifica el objeto (ej. encendedor), marcas, inscripciones visibles y estado. "
            "Estructura tu respuesta obligatoriamente en tres secciones:\n"
            "1. HECHOS:\n2. HIPÓTESIS:\n3. INCERTIDUMBRES / UNKNOWN:"
        )

        user_content = [
            {
                "type": "text",
                "text": f"Descripción: {object_description}\nNotas: {context_notes}. Analiza las evidencias visuales adjuntas."
            }
        ]

        # Procesamos como máximo las 2 primeras imágenes de forma optimizada
        if image_paths:
            for path in image_paths[:2]:
                if os.path.exists(path):
                    base64_img = self._optimize_and_encode_image(path)
                    user_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_img}"
                        }
                    })

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.2,
                timeout=300  # Ampliado a 300 segundos (5 minutos) para dar margen a la inferencia local
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error en la inferencia local con Ollama: {str(e)}"

LocalHermesExplorer = LocalAIAgent