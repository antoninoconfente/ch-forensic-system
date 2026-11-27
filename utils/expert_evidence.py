"""Evidencia pericial manual del experto humano (Human-in-the-Loop)."""

from __future__ import annotations

import time
from typing import Any

from agents.schemas import ExpertEvidenceEntry


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
                "image_path": str(item.get("image_path") or "").strip() or None,
                "timestamp": float(item.get("timestamp") or time.time()),
            }
        )
    return out


def expert_evidence_synthesis(entries: list | None) -> str:
    """Texto consolidado para la directiva de resolución."""
    lines: list[str] = []
    for item in normalize_expert_evidence(entries if isinstance(entries, list) else []):
        note = item.get("text_note") or ""
        img = item.get("image_path") or ""
        if img:
            lines.append(f"{note} [Evidencia fotográfica anexa: {img}]")
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
    paths: list[str] = []
    for item in normalize_expert_evidence(entries if isinstance(entries, list) else []):
        p = str(item.get("image_path") or "").strip()
        if p and p not in paths:
            paths.append(p)
    return paths