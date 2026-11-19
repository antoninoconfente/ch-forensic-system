"""Compatibilidad: delega en el motor editorial de `utils.pdf_exporter`."""

from utils.pdf_exporter import generate_dossier_pdf


def build_dossier_pdf(
    case_id: str,
    title: str,
    dictamen: str,
    image_paths: list,
    metadata: dict | None = None,
) -> bytes:
    """API legada — conservada para scripts y pruebas existentes."""
    meta = dict(metadata or {})
    case_data = {
        "case_id": case_id,
        "title": title,
        "dictamen_text": dictamen,
        "object_description": meta.get("object_description") or title,
        "timestamp": meta.get("timestamp"),
        "gemology_data": meta.get("gemology_data"),
        "cad_blueprint": meta.get("cad_blueprint") or {},
        "forensic_report": meta.get("forensic_report") or {},
        "market_valuation_report": meta.get("market_valuation_report") or {},
        "logistics_arbitrage_report": meta.get("logistics_arbitrage_report") or {},
        "logistics_intelligence": meta.get("logistics_intelligence") or {},
        "domain_taxonomy": meta.get("domain_taxonomy") or "",
        "maker": meta.get("maker") or "",
    }
    return generate_dossier_pdf(case_data, image_paths)