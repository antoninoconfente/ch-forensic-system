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
    propagate_audit_trail_to_root(metadata)
    master = concat_phase_audit_trails(metadata)
    if master:
        metadata["master_global_audit_trail"] = master
    return metadata


def _lines_from_blob(blob: dict | None) -> list[str]:
    if not isinstance(blob, dict):
        return []
    raw = blob.get("global_audit_trail") or []
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


def get_full_audit_trail(expediente: dict | None) -> list[str]:
    """Barre raíz y sub-bloques (nombres legacy y actuales) sin duplicados."""
    if not isinstance(expediente, dict):
        return []

    ordered: list[str] = []

    def _append_many(lines: list[str]) -> None:
        for line in lines:
            if line and line not in ordered:
                ordered.append(line)

    master = expediente.get("master_global_audit_trail")
    if isinstance(master, list) and master:
        _append_many([str(x).strip() for x in master if str(x).strip()])

    _append_many(_lines_from_blob(expediente))

    nested_keys = (
        "forensic_report",
        "market_valuation_report",
        "market_valuation",
        "logistics_arbitrage_report",
        "logistics_arbitrage",
    )
    for key in nested_keys:
        _append_many(_lines_from_blob(expediente.get(key)))

    return ordered


def propagate_audit_trail_to_root(metadata: dict) -> dict:
    """Copia entradas de sub-informes a expediente['global_audit_trail'] (concat, sin pisar)."""
    if not isinstance(metadata, dict):
        return metadata
    root: list[str] = list(metadata.get("global_audit_trail") or [])
    seen = {str(x).strip() for x in root if str(x).strip()}

    for key in (
        "forensic_report",
        "market_valuation_report",
        "market_valuation",
        "logistics_arbitrage_report",
        "logistics_arbitrage",
    ):
        for line in _lines_from_blob(metadata.get(key)):
            if line not in seen:
                root.append(line)
                seen.add(line)

    metadata["global_audit_trail"] = root
    return metadata