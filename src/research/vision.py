import base64
import os
from typing import Any, Dict
from openai import OpenAI
from pydantic import BaseModel, Field


class VisualObservationResult(BaseModel):
    status: str = "MODEL_REPORTED_UNVERIFIED"
    model_name: str
    raw_response: Dict[str, Any]
    normalized_observations: Dict[str, Any]


class OpenAIControlledVisionClient:
    """Cliente controlado para análisis visual multimodal con marcado epistemológico estricto."""

    def __init__(self, model_name: str = "gpt-4o"):
        self.model_name = model_name
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key) if api_key else None

    def analyze_image(self, image_path: str, prompt: str) -> VisualObservationResult:
        """Envía una imagen a OpenAI bajo estrictas condiciones controladas usando el SDK moderno."""
        if not self.client:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError(
                    "OPENAI_API_KEY no está configurada en el entorno (.env)."
                )
            self.client = OpenAI(api_key=api_key)

        # Codificar imagen en base64
        with open(image_path, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode("utf-8")

        try:
            # Llamada al cliente moderno de OpenAI (v1.0+)
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Eres un asistente de investigación de objetos históricos. "
                            "Tus observaciones son estrictamente no verificadas y deben reportarse como hipótesis visuales, "
                            "nunca como identidad física o autenticidad absoluta."
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{encoded_image}"
                                },
                            },
                        ],
                    },
                ],
                max_tokens=1000,
            )

            raw_output = response.model_dump() if hasattr(response, "model_dump") else dict(response)
            content_text = response.choices[0].message.content

            return VisualObservationResult(
                status="MODEL_REPORTED_UNVERIFIED",
                model_name=self.model_name,
                raw_response=raw_output,
                normalized_observations={
                    "description": content_text,
                    "confidence_caveat": "Unverified visual observation; requires documentary corroboration.",
                },
            )

        except Exception as e:
            raise RuntimeError(f"MODEL_INTERFACE_FAILED: {str(e)}")
