"""Evidencia pericial manual del experto humano (Human-in-the-Loop)."""

from __future__ import annotations

import time

from agents.schemas import ExpertEvidenceEntry


def _image_paths_from_dict(item: dict) -> list[str]:
    paths: list[str] = []
    raw_list = item.get("image_paths")
    if isinstance(raw_list, list):
        for entry in raw_list:
            text = str(entry or "").strip()
            if text and text not in paths:
                paths.append(text)
    legacy = str(item.get("image_path") or "").strip()
    if legacy and legacy not in paths:
        paths.append(legacy)
    return paths


def normalize_expert_evidence(raw: list | None) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw:
        if isinstance(item, ExpertEvidenceEntry):
            out.append(item.model_dump())
            continue
        if not isinstance(item, dict):
            continue
        note = str(item.get("text_note") or "").strip()
        if not note:
            continue
        out.append(
            {
                "text_note": note,
                "image_paths": _image_paths_from_dict(item),
                "timestamp": float(item.get("timestamp") or time.time()),
            }
        )
    return out


def expert_evidence_synthesis(entries: list | None) -> str:
    """Texto consolidado para la directiva de resolución."""
    lines: list[str] = []
    for item in normalize_expert_evidence(entries if isinstance(entries, list) else []):
        note = item.get("text_note") or ""
        imgs = item.get("image_paths") or []
        if imgs:
            joined = "; ".join(str(p) for p in imgs[:6])
            suffix = f" (+{len(imgs) - 6} más)" if len(imgs) > 6 else ""
            lines.append(f"{note} [Evidencias fotográficas: {joined}{suffix}]")
        else:
            lines.append(note)
    return " /// ".join(lines)


def build_expert_resolution_prompt_block(expert_evidence: list | None) -> str:
    texto = expert_evidence_synthesis(expert_evidence)
    if not texto:
        return ""
    return (
        "ATENCIÓN - DIRECTIVA DE RESOLUCIÓN PERICIAL: "
        f"El experto humano ha aportado pruebas de laboratorio o nueva información concluyente: '{texto}'. "
        "Tienes TERMINANTEMENTE PROHIBIDO generar hipótesis alternativas, dudar de esta información o crear "
        "Escenarios A y B contradictorios. Debes colapsar tus escenarios y generar un ÚNICO escenario de "
        "valoración definitivo (Escenario Pericial Confirmado) basado 100% en esta prueba aportada, "
        "descartando cualquier simulación o duda anterior."
    )


def expert_evidence_image_paths(entries: list | None) -> list[str]:
    """Todas las rutas de imagen de todos los anexos (orden estable, sin duplicados)."""
    paths: list[str] = []
    for item in normalize_expert_evidence(entries if isinstance(entries, list) else []):
        for p in item.get("image_paths") or []:
            text = str(p or "").strip()
            if text and text not in paths:
                paths.append(text)
    return paths