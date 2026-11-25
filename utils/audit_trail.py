"""Consolidación de caja negra multi-agente en el expediente."""

from __future__ import annotations


def concat_phase_audit_trails(metadata: dict | None) -> list[str]:
    if not isinstance(metadata, dict):
        return []
    merged: list[str] = []
    for phase, key in (
        ("FORENSE", "forensic_report"),
        ("TASACIÓN", "market_valuation_report"),
        ("LOGÍSTICA", "logistics_arbitrage_report"),
    ):
        blob = metadata.get(key)
        if not isinstance(blob, dict):
            continue
        for line in blob.get("global_audit_trail") or []:
            text = str(line).strip()
            if not text:
                continue
            if text.startswith("["):
                merged.append(text)
            else:
                merged.append(f"[{phase}] {text}")
    return merged


def sync_master_global_audit_trail(metadata: dict) -> dict:
    """Persiste vista maestra concatenada (no sobrescribe trails por agente)."""
    master = concat_phase_audit_trails(metadata)
    if master:
        metadata["master_global_audit_trail"] = master
    return metadata