"""Detección estricta de joyería/gemología vs. otras disciplinas."""

from __future__ import annotations

import re

from agents.schemas import normalize_snake_key
from database.client import get_domain_rubric
from src.research.gemology import GEM_SPECIES, normalize_gemology_data

_GEM_KEYWORDS = re.compile(r"\b(gema[s]?|joya[s]?)\b", re.I)


def _safe_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def explicit_parent_domain(case_data: dict) -> str:
    """Solo el parent_domain declarado en el informe forense (sin inferir por taxonomía)."""
    forensic = _safe_dict((case_data or {}).get("forensic_report"))
    raw = forensic.get("parent_domain")
    if raw:
        return normalize_snake_key(str(raw))
    return ""


def resolve_parent_domain(case_data: dict) -> str:
    """Parent explícito o, para etiquetas UI, inferencia de respaldo."""
    parent = explicit_parent_domain(case_data)
    if parent:
        return parent
    from agents.schemas import infer_parent_domain

    forensic = _safe_dict((case_data or {}).get("forensic_report"))
    tax = forensic.get("taxonomy_key") or (case_data or {}).get("domain_taxonomy") or ""
    if tax:
        return infer_parent_domain(str(tax))
    return ""


def resolve_discipline_label(case_data: dict) -> str:
    forensic = _safe_dict((case_data or {}).get("forensic_report"))
    if forensic.get("category_name"):
        return str(forensic["category_name"]).strip()
    tax = forensic.get("taxonomy_key") or (case_data or {}).get("domain_taxonomy") or ""
    if tax:
        try:
            row = get_domain_rubric(str(tax))
            if row and getattr(row, "display_name", None):
                return str(row.display_name).strip()
        except Exception:
            pass
    parent = explicit_parent_domain(case_data) or resolve_parent_domain(case_data)
    if parent:
        return parent.replace("_", " ").title()
    return "Objetos de colección"


def resolve_materials_label(case_data: dict) -> str:
    forensic = _safe_dict((case_data or {}).get("forensic_report"))
    materials = forensic.get("primary_materials") or forensic.get("materials") or []
    if isinstance(materials, list) and materials:
        return ", ".join(str(m).strip() for m in materials if str(m).strip())
    if isinstance(materials, str) and materials.strip():
        return materials.strip()
    grade = str(forensic.get("purity_or_grade") or "").strip()
    weight = str(forensic.get("estimated_weight_or_volume") or "").strip()
    bits = [b for b in (grade, weight) if b]
    return " · ".join(bits) if bits else "—"


def _category_declares_gems(case_data: dict) -> bool:
    forensic = _safe_dict((case_data or {}).get("forensic_report"))
    blob = " ".join(
        str(forensic.get(key) or "")
        for key in ("category_name", "taxonomy_key", "technical_summary")
    )
    blob += " " + str((case_data or {}).get("domain_taxonomy") or "")
    return bool(_GEM_KEYWORDS.search(blob))


def _explicit_gems_detected(case_data: dict) -> bool:
    forensic = _safe_dict((case_data or {}).get("forensic_report"))
    gem = normalize_gemology_data(_safe_dict((case_data or {}).get("gemology_data")))

    if gem.get("has_gems") is True:
        return True

    g = _safe_dict(gem.get("gem"))
    p = _safe_dict(gem.get("pearl"))
    default_species = GEM_SPECIES[0] if GEM_SPECIES else ""
    species = str(g.get("species") or "").strip()
    if species and species != default_species:
        return True
    if float(g.get("carat") or 0) > 0:
        return True
    if int(p.get("count") or 0) > 0:
        return True

    for material in forensic.get("primary_materials") or []:
        low = str(material).lower()
        if any(w in low for w in ("diamante", "esmeralda", "rubí", "rubi", "zafiro", "gema", "perla", "brillante")):
            return True

    attrs = _safe_dict(forensic.get("key_attributes"))
    joined = " ".join(str(v) for v in attrs.values()).lower()
    return bool(_GEM_KEYWORDS.search(joined) or "diamante" in joined or "quilate" in joined)


def is_jewelry_or_gemology(case_data: dict) -> bool:
    """
    Criterio estricto:
    - parent_domain explícito JOYERIA → True
    - parent_domain RELOJERIA + gemas explícitas → True
    - categoría/taxonomía con «joya» o «gema» → True
    - En cualquier otro caso → False (arte, encendedores, destilados, mobiliario…)
    """
    case_data = case_data or {}
    forensic = _safe_dict(case_data.get("forensic_report"))

    if _category_declares_gems(case_data):
        return True

    parent = explicit_parent_domain(case_data)
    if parent == "JOYERIA":
        return True
    if parent == "RELOJERIA" and _explicit_gems_detected(case_data):
        return True

    return False


def format_gemology_status_line(gem: dict) -> str:
    """Solo usar cuando is_jewelry_or_gemology es True. Nunca inventa «Diamante» por defecto."""
    gem = normalize_gemology_data(gem or {})
    if not gem.get("applies") and not _explicit_gems_detected({"gemology_data": gem, "forensic_report": {}}):
        return "Sin gemas consignadas"
    g = _safe_dict(gem.get("gem"))
    p = _safe_dict(gem.get("pearl"))
    species = str(g.get("species") or "").strip()
    default_species = GEM_SPECIES[0] if GEM_SPECIES else ""
    carat = float(g.get("carat") or 0)
    pearl_n = int(p.get("count") or 0)
    parts = []
    if species and species != default_species:
        parts.append(species)
    elif carat > 0:
        parts.append("Gemas (especie por confirmar)")
    if carat > 0:
        parts.append(f"{carat:.2f} ct")
    if pearl_n > 0:
        parts.append(f"{pearl_n} perla(s)")
    metal = str(_safe_dict(gem.get("metal")).get("kind") or "").strip()
    if metal and not parts:
        return f"Montura — {metal}"
    return " · ".join(parts) if parts else "Módulo gemológico — datos pendientes"


def measurement_guide_for_case(case_data: dict) -> str:
    forensic = _safe_dict((case_data or {}).get("forensic_report"))
    tax = forensic.get("taxonomy_key") or (case_data or {}).get("domain_taxonomy") or ""
    if tax:
        try:
            row = get_domain_rubric(str(tax))
            if row and (row.cad_measurement_guide or "").strip():
                return str(row.cad_measurement_guide).strip()
        except Exception:
            pass
    cad = _safe_dict((case_data or {}).get("cad_blueprint"))
    if str(cad.get("measurement_guide") or "").strip():
        return str(cad["measurement_guide"]).strip()
    return (
        "Registre cotas lineales en milímetros (X, Y, Z) y el peso total en gramos "
        "verificado en mano, según la guía de la rúbrica de la pieza."
    )


def forensic_dimensions_dict(case_data: dict) -> dict:
    forensic = _safe_dict((case_data or {}).get("forensic_report"))
    dims = forensic.get("dimensions_mm")
    return dims if isinstance(dims, dict) else {}


SERIAL_FICHA_ROWS: tuple[tuple[str, str], ...] = (
    ("serial_number_raw", "Nº de serie / referencia"),
    ("serial_format_analysis", "Análisis estructural (serie)"),
    ("serial_dating_inference", "Datación (serie)"),
    ("serial_authenticity_impact", "Coherencia autenticidad (serie)"),
)


def serial_decoding_ficha_rows(case_data: dict) -> list[tuple[str, str]]:
    """Filas para /// FICHA TÉCNICA RESUMIDA cuando hay decodificación de serie."""
    forensic = _safe_dict((case_data or {}).get("forensic_report"))
    sd = forensic.get("serial_decoding")
    if isinstance(sd, dict):
        source = {k: str(sd.get(k) or "").strip() for k, _ in SERIAL_FICHA_ROWS}
    else:
        attrs = _safe_dict(forensic.get("key_attributes"))
        source = {k: str(attrs.get(k) or "").strip() for k, _ in SERIAL_FICHA_ROWS}
    if not any(source.values()):
        return []
    return [(label, source[key]) for key, label in SERIAL_FICHA_ROWS if spec_value_is_present(source.get(key))]


def spec_value_is_present(value) -> bool:
    """False para vacío, None o marcadores de ausencia editorial."""
    if value is None:
        return False
    s = str(value).strip()
    if not s:
        return False
    if s in {"—", "-", "–", "N/A", "n/a", "SIN DATO", "sin dato"}:
        return False
    return True


def resolve_mass_grams(case_data: dict) -> str:
    cad = _safe_dict((case_data or {}).get("cad_blueprint"))
    for key in ("peso_total_g", "weight_g", "mass_g"):
        if cad.get(key) not in (None, "", 0):
            return str(cad.get(key))
    forensic = _safe_dict((case_data or {}).get("forensic_report"))
    return str(forensic.get("estimated_weight_or_volume") or "").strip() or "—"