"""Métricas de consumo Gemini y errores API compartidos."""

from __future__ import annotations


class GeminiAPIError(RuntimeError):
    """Fallo definitivo tras reintentos contra la API Gemini."""


def api_metrics_line_from_response(response) -> str | None:
    """Extrae línea [API METRICS] si usage_metadata está disponible."""
    if response is None:
        return None
    meta = getattr(response, "usage_metadata", None)
    if meta is None and hasattr(response, "model_dump"):
        try:
            dumped = response.model_dump()
            meta = dumped.get("usage_metadata") if isinstance(dumped, dict) else None
        except Exception:
            meta = None
    if isinstance(meta, dict):
        prompt_count = meta.get("prompt_token_count")
        candidates_count = meta.get("candidates_token_count")
    else:
        prompt_count = getattr(meta, "prompt_token_count", None) if meta is not None else None
        candidates_count = getattr(meta, "candidates_token_count", None) if meta is not None else None
    try:
        input_tokens = int(prompt_count) if prompt_count is not None else 0
        output_tokens = int(candidates_count) if candidates_count is not None else 0
    except (TypeError, ValueError):
        return None
    if input_tokens <= 0 and output_tokens <= 0:
        return None
    return (
        f"[API METRICS] Consumo: {input_tokens} tokens (prompt) | {output_tokens} tokens (respuesta)."
    )


def append_api_metrics_lines(trail: list[str] | None, lines: list[str]) -> list[str]:
    if not lines:
        return list(trail or [])
    merged = list(trail or [])
    for line in lines:
        text = str(line or "").strip()
        if text and text not in merged:
            merged.append(text)
    return merged