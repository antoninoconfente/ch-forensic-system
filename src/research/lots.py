"""Lotes comerciales. Agrupa expedientes por referencia, sin escribir en su metadata."""

import json
import os
import uuid

from src.research.gemology import normalize_gemology_data, value_piece
from src.research.logistics import extract_appraisal

LOTS_PATH = os.path.join("data", "lots.json")

STRATEGIES = (
    "Subasta Premium",
    "Liquidación Rápida",
    "Colección Temática",
)

_EXIT = {
    "Subasta Premium": {
        "buyer": "Coleccionista especializado y sala de subastas de joyería fina",
        "market": "Salida en subasta con reserva, en sala de joyería fina o de objeto de colección.",
    },
    "Liquidación Rápida": {
        "buyer": "Comprador profesional y boutique de segunda mano",
        "market": "Venta directa con pago inmediato, priorizando la rotación sobre la prima de catálogo.",
    },
    "Colección Temática": {
        "buyer": "Coleccionista temático",
        "market": "Salida conjunta en feria, galería o tratado privado, con el relato del conjunto.",
    },
}


def blank_store() -> dict:
    return {"lots": []}


def load_lots() -> list:
    if not os.path.exists(LOTS_PATH):
        return []
    try:
        with open(LOTS_PATH, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    lots = payload.get("lots") if isinstance(payload, dict) else None
    return [lot for lot in lots or [] if isinstance(lot, dict) and lot.get("lot_id")]


def save_lots(lots: list) -> None:
    os.makedirs(os.path.dirname(LOTS_PATH), exist_ok=True)
    temporary = LOTS_PATH + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump({"lots": lots}, handle, indent=2, ensure_ascii=False)
    os.replace(temporary, LOTS_PATH)


def create_lot(name: str, strategy: str, case_ids: list) -> dict:
    cleaned = " ".join((name or "").split())
    if not cleaned:
        raise ValueError("El lote necesita un nombre.")
    if strategy not in STRATEGIES:
        raise ValueError("La estrategia no está en el catálogo.")
    lot = {
        "lot_id": f"LOT-{uuid.uuid4().hex[:4].upper()}",
        "name": cleaned,
        "strategy": strategy,
        "case_ids": _unique_ids(case_ids),
    }
    lots = load_lots()
    lots.append(lot)
    save_lots(lots)
    return lot


def update_lot_members(lot_id: str, case_ids: list) -> dict | None:
    lots = load_lots()
    target = None
    for lot in lots:
        if lot.get("lot_id") == lot_id:
            lot["case_ids"] = _unique_ids(case_ids)
            target = lot
            break
    if target is None:
        return None
    save_lots(lots)
    return target


def delete_lot(lot_id: str) -> bool:
    lots = load_lots()
    kept = [lot for lot in lots if lot.get("lot_id") != lot_id]
    if len(kept) == len(lots):
        return False
    save_lots(kept)
    return True


def _unique_ids(case_ids: list) -> list:
    seen = []
    for case_id in case_ids or []:
        text = str(case_id or "").strip()
        if text and text not in seen:
            seen.append(text)
    return seen


def piece_contribution(metadata: dict, dictamen: str, spot: dict | None = None) -> dict:
    """Lee la tasación ya guardada. No escribe el expediente."""
    record = normalize_gemology_data((metadata or {}).get("gemology_data"))
    valuation = record.get("valuation") if isinstance(record.get("valuation"), dict) else {}
    if record.get("applies") and not valuation:
        valuation = value_piece(record, spot or {})
    gem_total = float(valuation.get("gem_eur") or 0) + float(valuation.get("pearl_eur") or 0)
    metal = valuation.get("metal_eur")
    piece = valuation.get("piece_eur")
    if record.get("applies") and (piece not in (None, 0) or metal not in (None, 0)):
        return {
            "source": "gemología",
            "piece_eur": float(piece or 0),
            "metal_eur": float(metal or 0),
            "gem_eur": float(valuation.get("gem_eur") or 0),
            "pearl_eur": float(valuation.get("pearl_eur") or 0),
            "authorship_eur": float(valuation.get("authorship_eur") or 0),
            "setting_fee_eur": float(valuation.get("setting_fee_eur") or 0),
            "partial": bool(valuation.get("partial")),
        }
    if record.get("applies") and gem_total > 0:
        return {
            "source": "gemología",
            "piece_eur": float(piece or gem_total),
            "metal_eur": float(metal or 0),
            "gem_eur": float(valuation.get("gem_eur") or 0),
            "pearl_eur": float(valuation.get("pearl_eur") or 0),
            "authorship_eur": float(valuation.get("authorship_eur") or 0),
            "setting_fee_eur": float(valuation.get("setting_fee_eur") or 0),
            "partial": metal in (None, 0),
        }
    appraisal = extract_appraisal(dictamen or "")
    if appraisal.get("eur"):
        return {
            "source": "dictamen",
            "piece_eur": float(appraisal["eur"]),
            "metal_eur": 0.0,
            "gem_eur": 0.0,
            "pearl_eur": 0.0,
            "authorship_eur": 0.0,
            "setting_fee_eur": 0.0,
            "partial": False,
            "band": appraisal.get("range_label") or "",
        }
    return {
        "source": "pendiente",
        "piece_eur": None,
        "metal_eur": 0.0,
        "gem_eur": 0.0,
        "pearl_eur": 0.0,
        "authorship_eur": 0.0,
        "setting_fee_eur": 0.0,
        "partial": True,
    }


def summarize_lot(lot: dict, pieces: list) -> dict:
    """pieces: dicts con case_id, label, metadata y dictamen."""
    by_id = {piece.get("case_id"): piece for piece in pieces}
    rows = []
    missing = []
    for case_id in lot.get("case_ids") or []:
        piece = by_id.get(case_id)
        if not piece:
            missing.append(case_id)
            continue
        contribution = piece_contribution(piece.get("metadata") or {}, piece.get("dictamen") or "")
        rows.append({
            "case_id": case_id,
            "label": piece.get("label") or case_id,
            **contribution,
        })
    valued = [row for row in rows if row.get("piece_eur") is not None]
    pending = [row for row in rows if row.get("piece_eur") is None]
    total = round(sum(row["piece_eur"] for row in valued), 2)
    metal = round(sum(row["metal_eur"] for row in valued), 2)
    gems = round(sum(row["gem_eur"] for row in valued), 2)
    pearls = round(sum(row["pearl_eur"] for row in valued), 2)
    authorship = round(sum(row["authorship_eur"] for row in valued), 2)
    fees = round(sum(row["setting_fee_eur"] for row in valued), 2)
    strategy = lot.get("strategy") if lot.get("strategy") in STRATEGIES else STRATEGIES[0]
    exit_plan = dict(_EXIT[strategy])
    exit_plan["reason"] = _exit_reason(strategy, total, metal, gems + pearls, len(pending), len(valued))
    return {
        "lot_id": lot.get("lot_id"),
        "name": lot.get("name") or "",
        "strategy": strategy,
        "rows": rows,
        "missing": missing,
        "total_eur": total,
        "metal_eur": metal,
        "gem_eur": gems,
        "pearl_eur": pearls,
        "authorship_eur": authorship,
        "setting_fee_eur": fees,
        "valued_count": len(valued),
        "pending_count": len(pending),
        "exit": exit_plan,
    }


def _exit_reason(strategy: str, total: float, metal: float, stones: float, pending: int, valued: int) -> str:
    parts = []
    if pending:
        parts.append(f"{pending} pieza{'s' if pending != 1 else ''} siguen sin tasación cerrada y quedan fuera del acumulado.")
    if stones > metal and stones > 0:
        parts.append("El valor del conjunto pesa en gemas o perlas, así que el comprador natural es el coleccionista de piedra.")
    elif metal > stones and metal > 0 and strategy == "Liquidación Rápida":
        parts.append("El metal base sostiene una salida rápida hacia un comprador profesional.")
    elif valued and strategy == "Colección Temática":
        parts.append("La salida gana si las piezas se presentan juntas, con un solo relato de colección.")
    if strategy == "Subasta Premium" and valued > 1 and total < 1500:
        parts.append("El acumulado queda por debajo del umbral habitual de lote individual en sala; el conjunto se defiende mejor como un solo lote de catálogo.")
    elif strategy == "Subasta Premium" and total >= 1500:
        parts.append("El acumulado admite reserva de catálogo en una sala de joyería o de objeto de colección.")
    if not parts:
        parts.append("El perfil de salida sigue la estrategia elegida para el lote.")
    return " ".join(parts)
