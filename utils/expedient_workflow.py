"""Máquina de estados del expediente y sincronización post-orquestador."""

from __future__ import annotations

from utils.parsers import parse_dictamen_sections, pending_actionable_requests

FORMAL_ARCHIVE_STATUSES = frozenset({"active", "archived", "consolidated"})
WORKFLOW_DICTAMINADO = "DICTAMINADO"
WORKFLOW_EN_EVALUACION = "EN_EVALUACION"


def market_valuation_is_computed(market: dict | None) -> bool:
    if not isinstance(market, dict):
        return False
    invalid = frozenset({"", "—", "-", "n/a", "na", "pendiente", "sin inferencia"})

    def _ok(raw: object) -> bool:
        if isinstance(raw, (int, float)):
            return float(raw) > 0
        s = str(raw or "").strip()
        return s.casefold() not in invalid

    low_ok = _ok(market.get("estimated_value_low") or market.get("valuation_low"))
    high_ok = _ok(market.get("estimated_value_high") or market.get("valuation_high"))
    return low_ok or high_ok


def apply_expedient_state_transition(metadata: dict, dictamen_text: str = "") -> dict:
    """
    Si no hay dudas activas y hay tasación MoE, promueve status a dictaminado.
    No toca expedientes ya archivados formalmente (active/archived/consolidated).
    """
    meta = dict(metadata or {})
    status = str(meta.get("status") or "").lower()
    if status in FORMAL_ARCHIVE_STATUSES:
        return meta

    text = dictamen_text or meta.get("dictamen_text") or ""
    alerts, _ = parse_dictamen_sections(text)
    pending = pending_actionable_requests(meta, alerts)
    market = meta.get("market_valuation_report") or {}

    if not pending and market_valuation_is_computed(market):
        meta["status"] = "dictaminado"
        meta["workflow_state"] = WORKFLOW_DICTAMINADO
    else:
        meta["workflow_state"] = WORKFLOW_EN_EVALUACION
    return meta