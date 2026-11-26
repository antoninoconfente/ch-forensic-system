import html
import os
import sys
import time
from functools import partial
import requests
from PIL import Image
from nicegui import ui, app, run

# ---------------------------------------------------------
# BLINDAJE ABSOLUTO DE RUTAS DE IMPORTACIÓN (PATH RESOLUTION)
# ---------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from agents.orchestrator import ExpertCouncilOrchestrator, apply_user_resolutions_to_forensic_dict
from src.research.ai_agent import (
    LocalAIAgent,
    _compose_context_notes,
    apply_interrogation_update,
    relationalize_metadata,
)
from database.client import (
    compose_case_summary_for_embedding,
    delete_case as delete_cloud_case,
    get_case,
    get_signed_evidence_url,
    list_cases,
    save_case,
    upload_evidence_to_storage,
    upsert_case_embedding,
)
from database.models import Case, Evidence, GemologyData
from src.research.gemology import (
    AUTHORSHIPS,
    GEM_CLARITIES,
    GEM_COLORS,
    GEM_CUTS,
    GEM_NATURES,
    GEM_SPECIES,
    METALS,
    PEARL_LUSTER,
    PEARL_MATCHING,
    PEARL_NACRE,
    PEARL_NATURES,
    PEARL_SURFACE,
    SETTINGS,
    SUBJECTS,
    dictamen_section,
    format_eur as format_gem_eur,
    normalize_gemology_data,
    upsert_dictamen,
    value_piece,
)
from src.research.market_engine import MarketEngine
from utils.pdf_exporter import generate_dossier_pdf
from src.research.lots import (
    STRATEGIES,
    create_lot,
    delete_lot,
    load_lots,
    piece_contribution,
    summarize_lot,
    update_lot_members,
)
from src.research.logistics import (
    CUSTOM_CITY_OPTION,
    ORIGIN_GAZETTEER,
    build_logistics_intelligence,
    extract_appraisal,
    fold_place_name,
    format_eur,
    logistics_brief,
)

from auth.supabase_auth import (
    can_delete_in_archive,
    can_investigate,
    can_manage_lots,
    can_save_expedient,
    get_current_role,
    is_authenticated,
    role_display_label,
    sign_out,
)
from ui.theme import EDITORIAL_CSS, editorial_button, _web_img_src
from ui.views.login import build_login_page
from ui.blueprints import _infer_cad_defaults_from_dictamen
from ui.detail_discipline import (
    mount_admin_xray_dialog,
    xray_audit_visible,
    render_gemology_calculator,
    render_gemology_empty_state,
    render_jewelry_cad_laboratory,
    render_logistics_arbitrage_report,
    render_physical_metrology_block,
    render_public_ficha_spec_table,
    render_resolved_requests_history,
)
from utils.discipline import (
    is_jewelry_or_gemology,
    resolve_discipline_label,
    resolve_materials_label,
    serial_decoding_ficha_rows,
    spec_value_is_present,
)
from utils.audit_trail import propagate_audit_trail_to_root, sync_master_global_audit_trail
from utils.markdown_format import renumber_markdown_headers
from utils.parsers import (
    _auto_seed_gemology_from_dictamen,
    _choice_options,
    _deduplicate_and_Categorize_dictamen,
    _extract_product_identity_from_dictamen,
    _extract_true_market_valuation,
    _humanize_audit_question,
    _is_substantive_answer,
    executive_findings,
    parse_dictamen_sections,
    pending_actionable_requests,
    unanswered_questions,
)

agent = LocalAIAgent()
expert_council = ExpertCouncilOrchestrator(legacy_agent=agent)
market_engine = MarketEngine()

os.makedirs("data/temp", exist_ok=True)

app.add_static_files("/data", "data")

# Borradores en memoria (expediente analizado pero aún no persistido en Supabase).
_DRAFT_CASES: dict[str, dict] = {}
# Caché de descargas de evidencias del bucket privado (misma sesión de proceso).
_EVIDENCE_DISK_CACHE: dict[str, str] = {}

ROMAN_NUMERALS = [
    "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
    "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX",
]



JEWELRY_RIGOR_INSTRUCTIONS = (
    "[DIRECTIVA PERICIAL OBLIGATORIA DE ALTA JOYERÍA Y GEMOLOGÍA]: "
    "1) ARQUITECTURA DE LA JOYA: Respeta estrictamente la tipología, perfil de banda (Shank), tipo de engaste y cotas CAD en mm aportadas por el perito. "
    "2) CONTEO Y QUILATAJE REAL: Usa exactamente el conteo de piedras centrales y laterales y el quilataje calculado por dimensiones en mm. "
    "3) HIPÓTESIS DE VALORACIÓN GEMOLÓGICA: Presenta SIEMPRE DOS ESCENARIOS en la tabla de valoración: "
    "Escenario A (Hipótesis Gema Natural de época/calidad comercial-fina) y Escenario B (Hipótesis Gema Sintética/Simulante o valor intrínseco de metal + hechura). "
    "4) INTERROGATORIO REALISTA: PROHIBIDO pedir lecturas de refractómetro (RI), espectroscopía, UV 365nm o filtro Chelsea. "
    "Pide únicamente cotas del plano técnico (Ø interno, ancho de banda, espesor, L×A de gemas), peso en gramos o resultado de comprobación con joyero."
)


def to_roman(idx: int) -> str:
    if 0 <= idx < len(ROMAN_NUMERALS):
        return ROMAN_NUMERALS[idx]
    return str(idx + 1)




# ==========================================
# GESTOR UNIVERSAL DE SUBIDA DE ARCHIVOS
# ==========================================
async def _extract_upload_bytes(e) -> tuple[str, bytes]:
    raw_name = getattr(e, "name", None)
    if not raw_name and hasattr(e, "file"):
        raw_name = getattr(e.file, "name", "evidence.jpg")
    raw_name = raw_name or "evidence.jpg"

    ext = os.path.splitext(raw_name)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        ext = ".jpg"
    safe_name = f"ev_{os.urandom(3).hex()}{ext}"

    if hasattr(e, "content") and e.content is not None:
        data = e.content.read()
        if hasattr(data, "__await__"):
            data = await data
    elif hasattr(e, "file") and e.file is not None:
        read_res = e.file.read()
        data = await read_res if hasattr(read_res, "__await__") else read_res
    else:
        data = b""

    return safe_name, data





def _is_remote_src(path: str) -> bool:
    return bool(path) and str(path).startswith(("http://", "https://"))


def _media_src(path: str) -> str:
    if not path:
        return ""
    if _is_remote_src(path):
        return path
    if os.path.exists(path):
        return _web_img_src(path)
    return get_signed_evidence_url(path) or ""


def _gallery_image_src(item: dict) -> str:
    """URL absoluta firmada (o local) para la miniatura de tarjeta de galería."""
    candidates: list[str] = []
    main_path = (item.get("image_path") or "").strip()
    if main_path:
        candidates.append(main_path)
    for path in item.get("evidence_urls") or []:
        path = (path or "").strip()
        if path and path not in candidates:
            candidates.append(path)
    for path in candidates:
        if _is_remote_src(path):
            return path
        if os.path.exists(path):
            return _web_img_src(path)
        signed = get_signed_evidence_url(path)
        if signed:
            return signed
    return ""


def _bucket_object_path(src: str) -> str | None:
    if not src or _is_remote_src(src):
        return None
    if os.path.exists(src):
        return None
    cleaned = str(src).strip().lstrip("/")
    if cleaned.startswith("cases/"):
        return cleaned
    if cleaned and "/" in cleaned and not os.path.isabs(cleaned):
        return _normalize_bucket_path_for_cache(cleaned)
    return None


def _normalize_bucket_path_for_cache(path: str) -> str:
    cleaned = str(path or "").lstrip("/")
    if cleaned.startswith("cases/"):
        return cleaned
    return f"cases/{cleaned}"


def _fetch_evidence_to_cache(case_id: str, storage_path: str) -> str | None:
    key = _normalize_bucket_path_for_cache(storage_path)
    cached = _EVIDENCE_DISK_CACHE.get(key)
    if cached and os.path.exists(cached):
        return cached
    signed = get_signed_evidence_url(key)
    if not signed:
        return None
    folder = os.path.join("data", "temp", "evidence_cache", case_id or "case")
    os.makedirs(folder, exist_ok=True)
    ext = os.path.splitext(key)[1].lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        ext = ".jpg"
    destination = os.path.join(folder, f"{os.path.basename(key).split('.')[0] or 'evidence'}_{len(_EVIDENCE_DISK_CACHE)}{ext}")
    try:
        response = requests.get(signed, timeout=10)
        if response.status_code != 200:
            return None
        with open(destination, "wb") as handle:
            handle.write(response.content)
        _EVIDENCE_DISK_CACHE[key] = destination
        return destination
    except Exception:
        return None


def _materialize_image(src: str, folder: str, index: int, case_id: str = "case") -> str | None:
    if not src:
        return None
    if not _is_remote_src(src) and os.path.exists(src):
        return src
    bucket_path = _bucket_object_path(src)
    if bucket_path:
        cached = _fetch_evidence_to_cache(case_id, bucket_path)
        if cached:
            return cached
        return None
    if not _is_remote_src(src):
        signed = get_signed_evidence_url(src)
        if not signed:
            return None
        src = signed
    os.makedirs(folder, exist_ok=True)
    ext = os.path.splitext(str(src).split("?")[0])[1].lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        ext = ".jpg"
    destination = os.path.join(folder, f"evidence_{index + 1}{ext}")
    try:
        response = requests.get(src, timeout=10)
        if response.status_code != 200:
            return None
        with open(destination, "wb") as handle:
            handle.write(response.content)
        return destination
    except Exception:
        return None


def _analysis_image_paths(case_id: str, image_sources: list | None, allow_network: bool) -> list[str]:
    draft = _DRAFT_CASES.get(case_id)
    if draft:
        locals_ = [p for p in (draft.get("local_image_paths") or []) if p and os.path.exists(p)]
        if locals_:
            return locals_
    paths: list[str] = []
    for src in image_sources or []:
        if not src:
            continue
        if os.path.exists(src):
            paths.append(src)
            continue
        if allow_network:
            folder = os.path.join("data", "temp", "cloud", case_id or "case", "evidence")
            local = _materialize_image(src, folder, len(paths), case_id=case_id)
            if local:
                paths.append(local)
    return paths


def _scratch_case_folder(
    case_id: str,
    dictamen_text: str,
    image_sources: list,
    allow_network: bool = True,
) -> tuple[str, list]:
    folder = os.path.join("data", "temp", "cloud", case_id or "case")
    evidence_folder = os.path.join(folder, "evidence")
    os.makedirs(evidence_folder, exist_ok=True)
    with open(os.path.join(folder, "dictamen.md"), "w", encoding="utf-8") as handle:
        handle.write(dictamen_text or "")
    if case_id in _DRAFT_CASES:
        locals_ = _analysis_image_paths(case_id, image_sources, allow_network=False)
        return folder, locals_
    locals_ = _analysis_image_paths(case_id, image_sources, allow_network=allow_network)
    return folder, locals_


def get_case_view_model(case_id: str) -> dict:
    if not case_id:
        return {}
    if case_id in _DRAFT_CASES:
        return dict(_DRAFT_CASES[case_id])
    meta = cloud_case_metadata(case_id)
    return dict(meta) if meta else {}


def _persist_sources_from_metadata(case_id: str, metadata: dict) -> list:
    draft = _DRAFT_CASES.get(case_id)
    if draft and draft.get("local_image_paths"):
        return [p for p in draft["local_image_paths"] if p and os.path.exists(p)]
    urls = list(metadata.get("evidence_urls") or [])
    if not urls and metadata.get("image_path"):
        urls = [metadata["image_path"]]
    resolved: list = []
    for src in urls:
        if src and os.path.exists(src):
            resolved.append(src)
        elif src:
            resolved.append(src)
    return resolved


def _index_case_embedding_safe(case_id: str, metadata: dict, dictamen_text: str) -> None:
    try:
        meta = dict(metadata or {})
        forensic = meta.get("forensic_report") or {}
        taxonomy = (meta.get("domain_taxonomy") or forensic.get("taxonomy_key") or "").strip()
        summary = compose_case_summary_for_embedding(case_id, meta, dictamen_text)
        upsert_case_embedding(case_id, taxonomy, summary)
    except Exception as exc:
        print(f"[RAG] Indexación diferida omitida para {case_id}: {exc}", flush=True)


def _finalize_cloud_case(case_id: str, metadata: dict, dictamen_text: str, image_sources: list | None = None):
    metadata = dict(metadata or {})
    _preserve_draft_status_on_update(metadata, case_id)
    dictamen_text = renumber_markdown_headers(dictamen_text or "")
    sources = image_sources if image_sources is not None else _persist_sources_from_metadata(case_id, metadata)
    saved = persist_cloud_case(case_id, metadata, dictamen_text, sources)
    _index_case_embedding_safe(case_id, metadata, dictamen_text)
    _DRAFT_CASES.pop(case_id, None)
    return saved


def _case_is_draft(case_id: str) -> bool:
    return bool(case_id) and case_id in _DRAFT_CASES


def _case_archive_state(case_id: str) -> tuple[str, str]:
    """Etiqueta de cabecera y clase CSS editorial del badge."""
    if _case_is_draft(case_id):
        return "BORRADOR EN MEMORIA (NO GUARDADO)", "draft"
    row = get_case(case_id) if case_id else None
    if row and str(row.status or "").lower() == "draft":
        return "BORRADOR EN NUBE (SIN ARCHIVAR)", "draft"
    if row:
        return "ARCHIVADO EN NUBE", "archived"
    return "BORRADOR EN MEMORIA (NO GUARDADO)", "draft"


_FORMAL_ARCHIVE_STATUSES = frozenset({"active", "archived", "consolidated"})


def _case_is_formally_archived(case_id: str, metadata: dict | None = None) -> bool:
    """True solo cuando el usuario ya archivó formalmente el expediente."""
    if _case_is_draft(case_id):
        return False
    meta = dict(metadata or {})
    if case_id and not meta:
        meta = dict(get_case_view_model(case_id) or cloud_case_metadata(case_id) or {})
    status = str(meta.get("status") or "").lower()
    if status in _FORMAL_ARCHIVE_STATUSES:
        return True
    row = get_case(case_id) if case_id else None
    if row and str(row.status or "").lower() in _FORMAL_ARCHIVE_STATUSES:
        return True
    return False


def _case_needs_archive(case_id: str, metadata: dict | None = None) -> bool:
    """El botón de archivo se muestra mientras no esté formalmente archivado."""
    if _case_is_draft(case_id):
        return True
    meta = dict(metadata or {})
    if case_id and not meta.get("status"):
        meta = dict(get_case_view_model(case_id) or cloud_case_metadata(case_id) or {})
    status = str(meta.get("status") or "").lower()
    if status == "draft" or not status:
        return True
    if _case_is_formally_archived(case_id, meta):
        return False
    row = get_case(case_id) if case_id else None
    if row is None:
        return True
    return str(row.status or "").lower() == "draft"


def _preserve_draft_status_on_update(stored: dict, case_id: str) -> None:
    """Evita que un recálculo parcial promueva el expediente a 'active' por accidente."""
    current = str(stored.get("status") or "").lower()
    if current in _FORMAL_ARCHIVE_STATUSES:
        return
    row = get_case(case_id) if case_id else None
    db_status = str(row.status if row else current or "draft").lower()
    if db_status == "draft" or current == "draft" or not row:
        stored["status"] = "draft"


def _default_draft_title() -> str:
    return "Búsqueda Temporal (Sin Archivar)"


def _build_autosave_payload(
    case_id: str,
    investigation: dict,
    *,
    obj_desc: str,
    notes_val: str,
    market_context_notes: str,
    image_paths: list[str],
    dictamen_text: str,
) -> dict:
    """Metadatos listos para persistir en Supabase tras la inferencia."""
    draft_extras = investigation.get("draft_extras") or {}
    payload = {
        "case_id": case_id,
        "status": "draft",
        "custom_brand": "CH Hunter",
        "custom_title": _default_draft_title(),
        "object_description": obj_desc,
        "intake_notes": notes_val,
        "context_notes": market_context_notes,
        "dictamen_text": dictamen_text,
        "local_image_paths": list(image_paths),
        "evidence_urls": list(image_paths),
        "image_path": image_paths[0] if image_paths else "",
        "timestamp": time.time(),
        "gemology_data": {},
        "cad_blueprint": dict(draft_extras.get("cad_blueprint") or {}),
        "domain_taxonomy": draft_extras.get("domain_taxonomy") or "",
        "forensic_report": investigation.get("forensic_report") or draft_extras.get("forensic_report") or {},
        "market_valuation_report": investigation.get("market_valuation_report")
        or draft_extras.get("market_valuation_report")
        or {},
        "logistics_arbitrage_report": investigation.get("logistics_arbitrage_report")
        or draft_extras.get("logistics_arbitrage_report")
        or {},
        "question_answers": {},
        "resolved_questions": [],
        "logistics_intelligence": {},
        "successful_queries": draft_extras.get("successful_queries") or [],
        "master_global_audit_trail": investigation.get("master_global_audit_trail")
        or draft_extras.get("master_global_audit_trail")
        or [],
        "global_audit_trail": draft_extras.get("global_audit_trail") or [],
    }
    propagate_audit_trail_to_root(payload)
    sync_master_global_audit_trail(payload)
    return payload


def _gemology_columns(block: dict) -> dict:
    metal = (block or {}).get("metal") or {}
    gem = (block or {}).get("gem") or {}
    valuation = (block or {}).get("valuation") or {}
    grams = metal.get("grams")
    carats = gem.get("carat")
    piece = valuation.get("piece_eur")
    return {
        "applies": bool((block or {}).get("applies")),
        "subject": (block or {}).get("subject"),
        "metal_kind": metal.get("kind"),
        "metal_grams": float(grams) if grams not in (None, "") else None,
        "total_carats": float(carats) if carats not in (None, "") else None,
        "valuation_eur": float(piece) if piece not in (None, "") else None,
    }


def _metadata_from_case(case: Case) -> dict:
    records = sorted(case.gemology_records or [], key=lambda row: row.id or 0)
    evidences = sorted(case.evidences or [], key=lambda row: (not row.is_main, row.id or 0))
    raw = dict(records[0].raw_json or {}) if records else {}
    dossier = raw.pop("_dossier", {}) or {}
    if not isinstance(dossier, dict):
        dossier = {}
    main = next((row for row in evidences if row.is_main), None)
    image = (main or (evidences[0] if evidences else None))
    created = case.created_at.timestamp() if case.created_at else 0
    return {
        "case_id": case.id,
        "status": case.status or "active",
        "custom_brand": case.custom_brand,
        "custom_title": case.custom_title,
        "object_description": case.object_description or "",
        "intake_notes": case.intake_notes or "",
        "context_notes": case.context_notes or "",
        "dictamen_text": case.dictamen_text or "",
        "image_path": image.storage_path if image else "",
        "evidence_urls": [row.storage_path for row in evidences if row.storage_path],
        "folder_path": "",
        "gemology_data": raw,
        "cad_blueprint": dossier.get("cad_blueprint") or {},
        "question_answers": dossier.get("question_answers") or {},
        "resolved_questions": dossier.get("resolved_questions") or [],
        "logistics_intelligence": dossier.get("logistics_intelligence") or {},
        "successful_queries": dossier.get("successful_queries") or [],
        "timestamp": dossier.get("timestamp") or created,
        "domain_taxonomy": dossier.get("domain_taxonomy") or "",
        "forensic_report": dossier.get("forensic_report") or {},
        "market_valuation_report": dossier.get("market_valuation_report") or {},
        "logistics_arbitrage_report": dossier.get("logistics_arbitrage_report") or {},
        "master_global_audit_trail": dossier.get("master_global_audit_trail") or [],
        "global_audit_trail": dossier.get("global_audit_trail") or [],
        "manual_jewelry_mode": dossier.get("manual_jewelry_mode"),
    }


def cloud_case_items() -> list:
    """Orden cronológico, el más antiguo primero, como el archivo local."""
    return [_metadata_from_case(case) for case in reversed(list_cases())]


def cloud_case_metadata(case_id: str) -> dict:
    case = get_case(case_id) if case_id else None
    return _metadata_from_case(case) if case else {}


def _public_evidence_url(case_id: str, source: str, index: int) -> str | None:
    if _is_remote_src(source):
        return source
    if source and not os.path.exists(source):
        return str(source).lstrip("/")
    if not source or not os.path.exists(source):
        return None
    ext = os.path.splitext(source)[1].lower() or ".jpg"
    file_name = f"{case_id}/evidence_{index + 1}_{os.urandom(2).hex()}{ext}"
    return upload_evidence_to_storage(source, file_name)


def persist_cloud_case(
    case_id: str,
    metadata: dict,
    dictamen_text: str,
    image_sources: list | None = None,
    status: str | None = None,
) -> dict:
    meta = dict(metadata or {})
    gem_block = dict(meta.get("gemology_data") or {})
    raw_json = dict(gem_block)
    raw_json["_dossier"] = {
        "cad_blueprint": meta.get("cad_blueprint") or {},
        "question_answers": meta.get("question_answers") or {},
        "resolved_questions": meta.get("resolved_questions") or [],
        "logistics_intelligence": meta.get("logistics_intelligence") or {},
        "successful_queries": meta.get("successful_queries") or [],
        "timestamp": meta.get("timestamp"),
        "domain_taxonomy": meta.get("domain_taxonomy") or "",
        "forensic_report": meta.get("forensic_report") or {},
        "market_valuation_report": meta.get("market_valuation_report") or {},
        "logistics_arbitrage_report": meta.get("logistics_arbitrage_report") or {},
        "master_global_audit_trail": meta.get("master_global_audit_trail") or [],
        "global_audit_trail": meta.get("global_audit_trail") or [],
        "manual_jewelry_mode": meta.get("manual_jewelry_mode"),
    }
    columns = _gemology_columns(gem_block)
    sources = list(image_sources if image_sources is not None else meta.get("evidence_urls") or [])
    if not sources and meta.get("image_path"):
        sources = [meta["image_path"]]
    evidences = []
    for index, source in enumerate(sources):
        url = _public_evidence_url(case_id, source, index)
        if url:
            evidences.append(Evidence(case_id=case_id, storage_path=url, is_main=index == 0))
    case = Case(
        id=case_id,
        status=status or meta.get("status") or "active",
        custom_brand=(meta.get("custom_brand") or None),
        custom_title=(meta.get("custom_title") or None),
        object_description=meta.get("object_description") or "",
        intake_notes=meta.get("intake_notes") or "",
        context_notes=meta.get("context_notes") or "",
        dictamen_text=dictamen_text or "",
        gemology_records=[GemologyData(case_id=case_id, raw_json=raw_json, **columns)],
        evidences=evidences,
    )
    stored = save_case(case)
    return _metadata_from_case(stored)


def save_manual_jewelry_mode(case_id: str, enabled: bool) -> None:
    stored = get_case_view_model(case_id)
    if not stored:
        return
    stored["manual_jewelry_mode"] = bool(enabled)
    if enabled:
        gem_blk = normalize_gemology_data(stored.get("gemology_data"))
        gem_blk["applies"] = True
        stored["gemology_data"] = gem_blk
    if case_id in _DRAFT_CASES:
        _DRAFT_CASES[case_id] = stored
        return
    if get_case(case_id):
        _finalize_cloud_case(case_id, stored, stored.get("dictamen_text") or "")


def save_custom_identity(case_id: str, custom_brand: str, custom_title: str):
    stored = get_case_view_model(case_id)
    if not stored:
        return
    stored["custom_brand"] = (custom_brand or "").strip()
    stored["custom_title"] = (custom_title or "").strip()
    if case_id in _DRAFT_CASES:
        _DRAFT_CASES[case_id] = stored
    _finalize_cloud_case(case_id, stored, stored.get("dictamen_text") or "")


def save_cad_blueprint_and_recalculate(case_id: str, case_folder: str, metadata: dict, cad_data: dict) -> str:
    stored = dict(get_case_view_model(case_id) or metadata or {})

    stored["cad_blueprint"] = cad_data

    lines = [
        "[PLIEGO TÉCNICO CAD DE ALTA JOYERÍA VERIFICADO EN MANO (MANDATO ESTRUCTURAL ABSOLUTO)]:",
        f"- Tipología estructural: {cad_data.get('jewelry_type', 'Anillo / Sortija')}.",
        f"- Perfil de Banda / Brazo (Shank): {cad_data.get('shank_profile', 'Estándar')}.",
        f"- Arquitectura de Engaste: {cad_data.get('setting_arch', 'Estándar')}.",
    ]
    if cad_data.get("weight_g"):
        lines.append(f"- Peso bruto exacto en báscula: {cad_data['weight_g']} gramos.")
    if cad_data.get("cota_a_mm"):
        lines.append(f"- Cota A (Diámetro interno / Largo): {cad_data['cota_a_mm']} mm.")
    if cad_data.get("cota_b_mm"):
        lines.append(f"- Cota B (Ancho de banda / eslabón): {cad_data['cota_b_mm']} mm.")
    if cad_data.get("cota_c_mm"):
        lines.append(f"- Cota C (Espesor de aro / metal): {cad_data['cota_c_mm']} mm.")
    if cad_data.get("cota_d_mm"):
        lines.append(f"- Cota D (Altura de cabeza / galería): {cad_data['cota_d_mm']} mm.")

    if int(cad_data.get("central_count") or 0) > 0:
        lines.append(
            f"- Cota E (Gema Principal / Serie 1): {cad_data['central_count']} unidad(es) de {cad_data.get('central_species')} "
            f"en corte {cad_data.get('central_cut')}, medidas {cad_data.get('central_l_mm')} × {cad_data.get('central_w_mm')} × {cad_data.get('central_d_mm')} mm "
            f"(Quilataje geométrico estimado: {cad_data.get('central_ct')} ct)."
        )

    if int(cad_data.get("side_count") or 0) > 0:
        lines.append(
            f"- Cota F (Gemas Secundarias / Hombros / Serie 2 — CORREGIR CONTEO VISUAL CON ESTE DATO): "
            f"{cad_data['side_count']} unidad(es) de {cad_data.get('side_species')} en corte {cad_data.get('side_cut')}, "
            f"medidas {cad_data.get('side_l_mm')} × {cad_data.get('side_w_mm')} mm "
            f"(Quilataje geométrico total: {cad_data.get('side_ct')} ct)."
        )

    lines.append(f"- Quilataje Total Conjunto Calculado: {cad_data.get('total_ct', 0)} ct.")
    lines.append(f"- Hipótesis / Verificación Gemológica: {cad_data.get('gem_hypothesis', 'Evaluar Ambas Hipótesis')}.")
    if cad_data.get("extra_observations"):
        lines.append(f"- Observaciones de taller: {cad_data['extra_observations']}.")

    lines.append(JEWELRY_RIGOR_INSTRUCTIONS)
    spot_info = market_engine.get_metal_spot_prices()
    lines.append(f"[SPOT MARKET DATA - Gold: {spot_info.get('GOLD_EUR_PER_GRAM')}€/g, Silver: {spot_info.get('SILVER_EUR_PER_GRAM')}€/g]")

    base_notes = stored.get("intake_notes") or ""
    combined_context = f"{base_notes}\n\n" + "\n".join(lines)
    stored["context_notes"] = combined_context

    if cad_data.get("weight_g"):
        try:
            g_num = float(str(cad_data["weight_g"]).replace(",", "."))
            gem_blk = normalize_gemology_data(stored.get("gemology_data"))
            gem_blk["metal"]["grams"] = g_num
            if float(cad_data.get("total_ct") or 0) > 0:
                gem_blk["gem"]["carat"] = float(cad_data["total_ct"])
            stored["gemology_data"] = gem_blk
        except Exception:
            pass

    allow_net = case_id not in _DRAFT_CASES
    images = _analysis_image_paths(case_id, stored.get("evidence_urls") or [], allow_network=allow_net)
    updated = agent.analyze_evidence(
        object_description=stored.get("custom_title") or stored.get("object_description", "Joya peritada con plano CAD"),
        context_notes=combined_context,
        image_paths=images,
        case_id=case_id,
        persist_case=False,
    )
    if str(updated).startswith("[ERR") or str(updated).startswith("Error"):
        return updated
    stored["context_notes"] = combined_context
    stored["dictamen_text"] = updated
    if case_id in _DRAFT_CASES:
        _DRAFT_CASES[case_id] = stored
    else:
        _finalize_cloud_case(case_id, stored, updated)
    return updated




def commit_ficha_answers(
    case_id: str,
    case_folder: str,
    metadata: dict,
    pending_questions: list,
    answers_by_index: dict,
    files_by_index: dict,
    resolved_edits: dict | None = None,
    resolved_files: dict | None = None,
):
    stored = dict(get_case_view_model(case_id) or metadata or {})
    evidence_folder = os.path.join("data", "temp", "cloud", case_id or "case", "answers")
    os.makedirs(evidence_folder, exist_ok=True)
    new_locals = []
    newly_resolved = list(stored.get("resolved_questions") or [])
    resolved_edits = resolved_edits or {}
    resolved_files = resolved_files or {}
    for q_key, uploaded in resolved_files.items():
        if uploaded is None:
            continue
        name, content = uploaded
        extension = os.path.splitext(name)[1] or ".jpg"
        destination = os.path.join(
            evidence_folder,
            f"evidence_hist_{os.urandom(2).hex()}{extension}",
        )
        with open(destination, "wb") as handle:
            handle.write(content)
        new_locals.append(destination)
    for index, question in enumerate(pending_questions):
        answer = answers_by_index.get(index, "")
        answer = answer.strip() if isinstance(answer, str) else ""
        uploaded_bytes = files_by_index.get(index)
        if _is_substantive_answer(answer) and question not in newly_resolved:
            newly_resolved.append(question)
        if uploaded_bytes is not None:
            name, content = uploaded_bytes
            extension = os.path.splitext(name)[1] or ".jpg"
            destination = os.path.join(evidence_folder, f"evidence_q{index+1}_{os.urandom(2).hex()}{extension}")
            with open(destination, "wb") as handle:
                handle.write(content)
            new_locals.append(destination)

    updated_state = apply_interrogation_update(stored, pending_questions, answers_by_index)
    if resolved_edits:
        qa = dict(updated_state.get("question_answers") or {})
        for question, answer in resolved_edits.items():
            q = str(question or "").strip()
            if not q:
                continue
            qa[q] = answer.strip() if isinstance(answer, str) else ""
        updated_state["question_answers"] = qa
        intake = updated_state.get("intake_notes") or stored.get("intake_notes") or ""
        updated_state["prompt_context"] = _compose_context_notes(intake, qa)
    stored["resolved_questions"] = newly_resolved
    stored["intake_notes"] = updated_state["intake_notes"]
    stored["question_answers"] = updated_state["question_answers"]
    stored["context_notes"] = updated_state["intake_notes"]
    allow_net = case_id not in _DRAFT_CASES
    images = _analysis_image_paths(case_id, stored.get("evidence_urls") or [], allow_network=allow_net)
    images.extend(new_locals)
    prompt_ctx = (updated_state.get("prompt_context") or "") + "\n\n" + JEWELRY_RIGOR_INSTRUCTIONS
    prior_forensic = apply_user_resolutions_to_forensic_dict(
        stored.get("forensic_report") or {},
        pending_questions,
        answers_by_index,
        files_by_index,
        resolved_edits=resolved_edits,
        resolved_files=resolved_files,
    )
    stored["forensic_report"] = prior_forensic
    investigation = expert_council.run_investigation(
        stored.get("custom_title") or stored.get("object_description", "Pieza peritada"),
        prompt_ctx,
        images,
        case_id,
        agent,
        JEWELRY_RIGOR_INSTRUCTIONS,
        prior_forensic_report=prior_forensic,
        prior_case_extras={
            "market_valuation_report": stored.get("market_valuation_report"),
            "logistics_arbitrage_report": stored.get("logistics_arbitrage_report"),
        },
    )
    updated = investigation.get("dictamen_text") or ""
    if str(updated).startswith("[ERR") or str(updated).startswith("Error"):
        return updated
    stored["dictamen_text"] = updated
    extras = investigation.get("draft_extras") or {}
    if investigation.get("forensic_report"):
        stored["forensic_report"] = investigation["forensic_report"]
    elif extras.get("forensic_report"):
        stored["forensic_report"] = extras["forensic_report"]
    if extras.get("market_valuation_report"):
        stored["market_valuation_report"] = extras["market_valuation_report"]
    if extras.get("logistics_arbitrage_report"):
        stored["logistics_arbitrage_report"] = extras["logistics_arbitrage_report"]
    if extras.get("master_global_audit_trail"):
        stored["master_global_audit_trail"] = extras["master_global_audit_trail"]
    if investigation.get("master_global_audit_trail"):
        stored["master_global_audit_trail"] = investigation["master_global_audit_trail"]
    if investigation.get("global_audit_trail"):
        stored["global_audit_trail"] = investigation["global_audit_trail"]
    propagate_audit_trail_to_root(stored)
    sync_master_global_audit_trail(stored)
    if extras.get("cad_blueprint"):
        stored.setdefault("cad_blueprint", {}).update(extras["cad_blueprint"])
    _preserve_draft_status_on_update(stored, case_id)
    if case_id in _DRAFT_CASES:
        stored["local_image_paths"] = list(images)
        stored["evidence_urls"] = list(images)
        _DRAFT_CASES[case_id] = stored
    else:
        sources = list(stored.get("evidence_urls") or []) + new_locals
        _finalize_cloud_case(case_id, stored, updated, sources)
    return updated


def persist_logistics_intelligence(case_id: str, block: dict):
    stored = get_case_view_model(case_id)
    if not stored:
        return
    stored["logistics_intelligence"] = block
    if case_id in _DRAFT_CASES:
        _DRAFT_CASES[case_id] = stored
        return
    _finalize_cloud_case(case_id, stored, stored.get("dictamen_text") or "")


def persist_gemology(case_id: str, block: dict, dictamen_text: str) -> str:
    stored = get_case_view_model(case_id)
    if not stored:
        return dictamen_text
    block["_user_saved"] = True
    stored["gemology_data"] = block
    section = dictamen_section(block, block.get("valuation") or {})
    updated = renumber_markdown_headers(upsert_dictamen(dictamen_text, section))
    stored["dictamen_text"] = updated
    if case_id in _DRAFT_CASES:
        _DRAFT_CASES[case_id] = stored
    _finalize_cloud_case(case_id, stored, updated)
    return updated


def download_image_from_url(url, save_dir="data/temp"):
    os.makedirs(save_dir, exist_ok=True)
    try:
        session = requests.Session()
        if "drive.google.com" in url:
            if "/file/d/" in url:
                file_id = url.split("/file/d/")[1].split("/")[0]
            elif "id=" in url:
                file_id = url.split("id=")[1].split("&")[0]
            else:
                return None
            URL = "https://docs.google.com/uc?export=download"
            response = session.get(URL, params={'id': file_id}, stream=True, timeout=10)
        else:
            response = session.get(url, stream=True, timeout=10)

        if response.status_code == 200:
            filename = f"cloud_img_{os.urandom(2).hex()}.jpg"
            file_path = os.path.join(save_dir, filename)
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=32768):
                    if chunk:
                        f.write(chunk)
            try:
                with Image.open(file_path) as img:
                    img.verify()
                return file_path
            except Exception:
                if os.path.exists(file_path):
                    os.remove(file_path)
                return None
    except Exception:
        pass
    return None


def _lot_pieces() -> list:
    pieces = []
    for item in cloud_case_items():
        case_id = item.get("case_id")
        dictamen = item.get("dictamen_text") or ""
        maker, real_name = _extract_product_identity_from_dictamen(dictamen, item)
        pieces.append({
            "case_id": case_id,
            "maker": maker,
            "label": real_name,
            "metadata": item,
            "dictamen": dictamen,
            "image_path": item.get("image_path") or "",
            "folder": "",
        })
    return pieces


def _piece_thumbnail(piece: dict) -> str | None:
    image_path = piece.get("image_path") or ""
    if _is_remote_src(image_path) or (image_path and os.path.exists(image_path)):
        return image_path
    return None


def _piece_metrics(row: dict) -> str:
    if row.get("piece_eur") is None:
        return "Sin tasación cerrada"
    parts = [row.get("source") or "dictamen"]
    band = (row.get("band") or "").strip()
    if band:
        parts.append(band)
    if row.get("metal_eur"):
        parts.append(f"Metal {format_gem_eur(row['metal_eur'])}")
    if row.get("gem_eur"):
        parts.append(f"Gemas {format_gem_eur(row['gem_eur'])}")
    if row.get("pearl_eur"):
        parts.append(f"Perlas {format_gem_eur(row['pearl_eur'])}")
    return " · ".join(parts)


def _case_card_summary(item: dict) -> tuple[str, str, str, str]:
    cid = item.get("case_id")
    meta = item
    dictamen = item.get("dictamen_text") or ""

    maker, real_title = _extract_product_identity_from_dictamen(dictamen, meta)
    val_info = _extract_true_market_valuation(dictamen, meta)
    price_str = val_info["display"]

    findings = dict(executive_findings(dictamen))
    extra = findings.get("Datación") or findings.get("Acabado Noble") or findings.get("Contraste") or "Expediente autenticado"
    excerpt = f"Ref. {cid} · {extra}."
    if len(excerpt) > 85:
        excerpt = excerpt[:82].rstrip() + "…"

    return maker, real_title, price_str, excerpt


def _lot_brief_html(report: dict) -> str:
    exit_plan = report["exit"]
    piece_count = report["valued_count"] + report["pending_count"]
    fee = ""
    if report.get("setting_fee_eur"):
        fee = f"<div><span>Peritaje</span><strong>{format_gem_eur(report['setting_fee_eur'])}</strong></div>"
    return (
        "<div class='lot-brief'>"
        "<div class='lot-brief-top'>"
        "<div>"
        f"<p class='lot-kicker'>{html.escape(report['strategy'])} · {html.escape(str(report['lot_id']))}</p>"
        f"<h3 class='lot-title'>{html.escape(report['name'])}</h3>"
        f"<p class='lot-count'>{piece_count} {'pieza' if piece_count == 1 else 'piezas'}</p>"
        "</div>"
        "<div class='lot-total'>"
        "<p class='lot-kicker'>Tasación acumulada</p>"
        f"<p class='lot-figure'>{format_gem_eur(report['total_eur'])}</p>"
        "</div></div>"
        "<div class='lot-metrics'>"
        f"<div><span>Metal</span><strong>{format_gem_eur(report['metal_eur'])}</strong></div>"
        f"<div><span>Gemas</span><strong>{format_gem_eur(report['gem_eur'])}</strong></div>"
        f"<div><span>Perlas</span><strong>{format_gem_eur(report['pearl_eur'])}</strong></div>"
        f"<div><span>Autoría</span><strong>{format_gem_eur(report['authorship_eur'])}</strong></div>"
        f"{fee}</div>"
        "<div class='lot-exit'>"
        "<div><p class='lot-kicker'>Comprador</p>"
        f"<p>{html.escape(exit_plan['buyer'])}</p></div>"
        "<div><p class='lot-kicker'>Mercado</p>"
        f"<p>{html.escape(exit_plan['market'])}</p></div>"
        "</div>"
        f"<p class='lot-reason'>{html.escape(exit_plan['reason'])}</p>"
        "</div>"
    )


def _case_evidence_paths(folder: str, fallback: str = "") -> list:
    paths = []
    evidence = os.path.join(folder or "", "evidence")
    if os.path.isdir(evidence):
        for name in sorted(os.listdir(evidence)):
            if name.lower().endswith(("png", "jpg", "jpeg", "webp")):
                paths.append(os.path.join(evidence, name))
    if not paths and fallback and os.path.exists(fallback):
        paths.append(fallback)
    return paths


# ==========================================
# APLICACIÓN PRINCIPAL NICEGUI
# ==========================================
@ui.page("/login")
def login_page():
    build_login_page()


@ui.page("/")
def index_page():
    if not is_authenticated():
        ui.navigate.to("/login")
        return

    ui.add_head_html(EDITORIAL_CSS)
    ui.page_title("CH Curiosities Hunter")

    state = {
        "current_view": "main",
        "last_dictamen": "",
        "active_case_id": "",
        "selected_case_id": None,
        "uploaded_paths": [],
        "detail_tab": "sintesis",
    }

    with ui.dialog() as zoom_dialog, ui.card().classes("bg-[#F3EFE6] border border-[#141413] rounded-none p-4 max-w-3xl w-full shadow-none"):
        zoom_title = ui.label("").classes("micro-coord mb-2")
        zoom_img = ui.image("").classes("w-full max-h-[75vh] object-contain border border-[#141413]")
        with ui.row().classes("w-full justify-end mt-3"):
            editorial_button("CERRAR", on_click=zoom_dialog.close)

    def open_zoom(img_path: str, caption: str = ""):
        zoom_title.text = caption
        zoom_img.set_source(img_path)
        zoom_dialog.open()

    root_container = ui.column().classes("w-full max-w-[1360px] mx-auto px-4 md:px-10 py-6 gap-0")

    def navigate(view_name: str, case_id: str = None):
        state["current_view"] = view_name
        if case_id is not None:
            state["selected_case_id"] = case_id
            state["detail_tab"] = "sintesis"
        refresh_ui()

    def render_top_bar(section_code: str = "CH-01"):
        all_count = len(cloud_case_items())
        spot_info = market_engine.get_metal_spot_prices()
        session_email = (app.storage.user.get("auth_session") or {}).get("email") or ""
        role_badge = role_display_label(get_current_role())
        user_line = f"{html.escape(role_badge)}"
        if session_email:
            user_line += f" · {html.escape(session_email)}"
        with ui.row().classes("w-full justify-between items-center pb-2 border-b border-[#141413] mb-6"):
            with ui.column().classes("gap-1"):
                ui.html(f"<span class='micro-coord'>{html.escape(section_code)} // CH CURIOSITIES HUNTER</span>")
                ui.html(f"<span class='editorial-status-badge editorial-status-badge--archived'>{user_line}</span>")
            with ui.row().classes("gap-4 items-center"):
                editorial_button("PANEL PRINCIPAL", on_click=lambda: navigate("main"), small=True)
                ui.html("<span class='text-[#141413]'>/</span>")
                editorial_button(f"ARCHIVO ({all_count})", on_click=lambda: navigate("library"), small=True)
                ui.html("<span class='text-[#141413]'>/</span>")
                editorial_button("LOTES COMERCIALES", on_click=lambda: navigate("lots"), small=True)
                ui.html("<span class='text-[#141413]'>/</span>")

                def close_session():
                    sign_out()
                    ui.navigate.to("/login")

                editorial_button("CERRAR SESIÓN", on_click=close_session, small=True)
            ui.html(
                f"<span class='micro-coord text-[#141413]'>"
                f"SPOT ORO {spot_info.get('GOLD_EUR_PER_GRAM')} €/G · PLATA {spot_info.get('SILVER_EUR_PER_GRAM')} €/G"
                f"</span>"
            )

    def render_catalog_card(item: dict, idx: int, show_delete: bool = False):
        c_id = item.get("case_id")

        maker, real_title, price_str, excerpt = _case_card_summary(item)
        roman = to_roman(idx)
        web_src = _gallery_image_src(item)

        with ui.element("div").classes("catalog-card w-full"):
            with ui.column().classes("w-full gap-0"):
                if web_src:
                    with ui.element("div").classes(
                        "catalog-img-frame cursor-pointer hover:opacity-80 transition-opacity"
                    ).on("click", lambda _, cid=c_id: navigate("detail", cid)):
                        ui.image(web_src).props("fit=cover no-spinner").classes("w-full h-full")
                else:
                    ui.html("<div class='catalog-img-frame flex items-center justify-center'><span class='micro-coord'>SIN IMAGEN</span></div>")

                ui.html(f"<div class='catalog-roman'>{roman}</div>")
                ui.html(f"<div class='catalog-brand'>{html.escape(maker)}</div>")
                ui.html(
                    f"<div class='catalog-row'>"
                    f"<span class='catalog-title-text' title='{html.escape(real_title)}'>{html.escape(real_title)}</span>"
                    f"<span class='catalog-price-text'>{html.escape(price_str)}</span>"
                    f"</div>"
                )
                ui.html(f"<p class='catalog-excerpt'>{html.escape(excerpt)}</p>")

            if show_delete and can_delete_in_archive():
                with ui.row().classes("w-full justify-end items-center pt-2"):
                    def _del(cid=c_id):
                        delete_cloud_case(cid)
                        refresh_ui()

                    editorial_button("ELIMINAR", on_click=_del, small=True)

    def refresh_ui():
        root_container.clear()
        with root_container:
            view = state["current_view"]
            if view == "main":
                build_main_view()
            elif view == "result":
                build_result_view()
            elif view == "library":
                build_library_view()
            elif view == "lots":
                build_lots_view()
            elif view == "detail":
                build_detail_view()

    # ------------------------------------------
    # VISTA 1: MAIN PANEL
    # ------------------------------------------
    def build_main_view():
        render_top_bar("CH-CORE // 01")

        with ui.column().classes("w-full items-center py-6 border-b border-[#141413] mb-0"):
            ui.html("<h1 class='masthead-title text-center m-0'>CH CURIOSITIES HUNTER</h1>")
            ui.html(
                "<p class='micro-coord text-center mt-2 mb-0'>"
                "PERITAJE FORENSE · AUTENTICACIÓN DOCUMENTAL Y MATERIAL · BUYER SEARCH"
                "</p>"
            )

        with ui.column().classes("w-full py-8 border-b border-[#141413] gap-5"):
            if can_investigate():
                with ui.row().classes("w-full justify-between items-baseline"):
                    ui.html("<span class='micro-coord'>01 // CÁMARA DE INGESTA + EVIDENCIA HUMANA EN MANO</span>")
                    ui.html("<span class='micro-coord'>ANÁLISIS MULTIMODAL + GEMOLOGÍA ACTIVA</span>")
            else:
                ui.html(
                    "<p class='micro-coord text-[#625E57] m-0'>"
                    "Modo consulta: puede revisar expedientes archivados. La ingesta y el análisis activo requieren perfil analista o administrador."
                    "</p>"
                )

            if can_investigate():
                with ui.row().classes("w-full grid grid-cols-1 lg:grid-cols-12 gap-8 items-start"):
                    with ui.column().classes("lg:col-span-5 w-full gap-3"):
                        ui.html("<h2 class='text-4xl m-0'>Nuevo Peritaje Activo</h2>")
                        ui.html(
                            "<p class='text-xs text-[#625E57] leading-relaxed m-0'>"
                            "Suba las fotografías de la pieza y aporte cualquier dato físico verificado en mano "
                            "(peso, medidas en mm, conteo real de piedras o contrastes) para ajustar el ojo gemológico."
                            "</p>"
                        )
                        source_radio = ui.radio(["Archivos Locales", "URL / Google Drive"], value="Archivos Locales").props("inline dense color=dark").classes("mt-2")

                    with ui.column().classes("lg:col-span-7 w-full gap-3"):
                        state["uploaded_paths"] = []
                        upload_container = ui.column().classes("w-full gap-3")
                        preview_row = ui.row().classes("w-full flex-wrap gap-4")
    
                        def refresh_previews():
                            preview_row.clear()
                            with preview_row:
                                for idx, p in enumerate(state["uploaded_paths"]):
                                    if os.path.exists(p):
                                        w_src = _web_img_src(p)
                                        with ui.column().classes("thumb-strip-item gap-1").on("click", lambda _, path=p, i=idx: open_zoom(path, f"IMAGE 0{i+1}")):
                                            ui.html(f"<span class='micro-coord'>IMAGE 0{idx+1}</span>")
                                            ui.html(f"<div class='thumb-frame'><img src='{html.escape(w_src)}'/></div>")
    
                        async def handle_local_upload(e):
                            os.makedirs("data/temp", exist_ok=True)
                            safe_name, data = await _extract_upload_bytes(e)
                            if not data:
                                ui.notify("No se pudieron leer los bytes de la imagen.", type="negative")
                                return
                            tmp_p = os.path.join("data/temp", safe_name)
                            with open(tmp_p, "wb") as f:
                                f.write(data)
                            state["uploaded_paths"].append(tmp_p)
                            refresh_previews()
                            ui.notify(f"Evidencia fotográfica cargada ({len(state['uploaded_paths'])})", type="positive")
    
                        urls_input_ref = {"widget": None}
    
                        def render_source_input():
                            upload_container.clear()
                            state["uploaded_paths"] = []
                            preview_row.clear()
                            with upload_container:
                                if source_radio.value == "Archivos Locales":
                                    ui.upload(
                                        label="SELECCIONAR EVIDENCIAS FOTOGRÁFICAS (JPG, PNG)",
                                        multiple=True,
                                        auto_upload=True,
                                        on_upload=handle_local_upload
                                    ).props("accept=.jpg,.jpeg,.png,.webp flat").classes("w-full editorial-uploader")
                                else:
                                    urls_area = ui.textarea(
                                        label="Enlaces de imágenes (uno por línea)",
                                        placeholder="https://... o enlace compartido de Google Drive"
                                    ).classes("w-full px-3 border border-[#141413]")
                                    urls_input_ref["widget"] = urls_area
    
                                    def load_urls():
                                        state["uploaded_paths"] = []
                                        raw = urls_area.value or ""
                                        for u in [x.strip() for x in raw.split("\n") if x.strip()]:
                                            dl = download_image_from_url(u)
                                            if dl:
                                                state["uploaded_paths"].append(dl)
                                            else:
                                                ui.notify(f"No se pudo procesar el enlace: {u}", type="warning")
                                        refresh_previews()
    
                                    editorial_button("PREVISUALIZAR ENLACES", on_click=load_urls)
    
                        source_radio.on_value_change(lambda _: render_source_input())
                        render_source_input()
    
                        with ui.row().classes("w-full grid grid-cols-1 sm:grid-cols-3 gap-3"):
                            in_weight = ui.input(label="Peso en gramos (opcional)", placeholder="Ej. 4.8 g").classes("w-full px-2 border border-[#141413]")
                            in_dimensions = ui.input(label="Talla / Diámetro / Ancho (mm)", placeholder="Ej. Ø 17mm, banda 4mm").classes("w-full px-2 border border-[#141413]")
                            in_gems = ui.input(label="Conteo y medidas de piedras", placeholder="Ej. 7 esmeraldas y 5 diamantes (2.5mm)").classes("w-full px-2 border border-[#141413]")
    
                        extra_notes = ui.input(
                            label="CUÑOS VISIBLES, HISTORIA O NOTAS DE REFERENCIA",
                            placeholder="Ej. Contraste 750 en interior de aro, estuche original..."
                        ).classes("w-full px-3 py-1 border border-[#141413]")
    
                        status_label = ui.label("").classes("micro-coord text-[#8c6d28] hidden")
    
                        with ui.dialog().props("persistent") as ai_loading_dialog, ui.card().classes(
                            "w-full items-center justify-center bg-grey-10 text-white gap-6"
                        ).style("min-width: min(100vw, 100%); min-height: 100vh; border-radius: 0;"):
                            ui.spinner("dots", size="lg", color="green-4")
                            ui.label(
                                "Procesando Inteligencia Artificial... Por favor, espere."
                            ).classes("text-lg text-center px-6")

                        async def run_investigation():
                            if source_radio.value == "URL / Google Drive" and not state["uploaded_paths"] and urls_input_ref["widget"]:
                                raw = urls_input_ref["widget"].value or ""
                                for u in [x.strip() for x in raw.split("\n") if x.strip()]:
                                    dl = await run.io_bound(download_image_from_url, u)
                                    if dl:
                                        state["uploaded_paths"].append(dl)

                            if not state["uploaded_paths"]:
                                ui.notify("Por favor, aporte al menos una evidencia fotográfica válida.", type="warning")
                                return

                            ai_loading_dialog.open()
                            status_label.text = "⏳ ANALIZANDO EVIDENCIAS EN SEGUNDO PLANO (SIN DESCONEXIÓN DE SERVIDOR)..."
                            status_label.classes(remove="hidden")
                            try:
                                spot_info = market_engine.get_metal_spot_prices()
                                case_id = f"EXP-CH-{os.urandom(2).hex().upper()}"

                                human_parts = []
                                if (in_weight.value or "").strip():
                                    human_parts.append(f"Peso físico: {in_weight.value.strip()}")
                                if (in_dimensions.value or "").strip():
                                    human_parts.append(f"Medidas/Diámetro/Banda: {in_dimensions.value.strip()}")
                                if (in_gems.value or "").strip():
                                    human_parts.append(
                                        f"Conteo y medidas reales de gemas verificadas por humano: {in_gems.value.strip()}"
                                    )
                                if (extra_notes.value or "").strip():
                                    human_parts.append(f"Notas adicionales: {extra_notes.value.strip()}")

                                notes_val = " | ".join(human_parts)
                                obj_desc = (
                                    notes_val
                                    if notes_val
                                    else "Pieza de joyería/colección analizada por visión artificial"
                                )
                                market_context_notes = (
                                    f"{notes_val}\n\n{JEWELRY_RIGOR_INSTRUCTIONS}\n"
                                    f"[SPOT MARKET DATA - Gold: {spot_info.get('GOLD_EUR_PER_GRAM')}€/g, "
                                    f"Silver: {spot_info.get('SILVER_EUR_PER_GRAM')}€/g]"
                                )

                                council_fn = partial(
                                    expert_council.run_investigation,
                                    obj_desc,
                                    market_context_notes,
                                    list(state["uploaded_paths"]),
                                    case_id,
                                    agent,
                                    JEWELRY_RIGOR_INSTRUCTIONS,
                                )
                                investigation = await run.io_bound(council_fn)
                                dictamen_text = renumber_markdown_headers(
                                    investigation.get("dictamen_text", "")
                                )
                                if str(dictamen_text).startswith("[ERR"):
                                    ui.notify(str(dictamen_text), type="negative")
                                    return

                                autosave_meta = _build_autosave_payload(
                                    case_id,
                                    investigation,
                                    obj_desc=obj_desc,
                                    notes_val=notes_val,
                                    market_context_notes=market_context_notes,
                                    image_paths=list(state["uploaded_paths"]),
                                    dictamen_text=dictamen_text,
                                )
                                await run.io_bound(
                                    _finalize_cloud_case,
                                    case_id,
                                    autosave_meta,
                                    dictamen_text,
                                    list(state["uploaded_paths"]),
                                )

                                state["last_dictamen"] = dictamen_text
                                state["active_case_id"] = case_id
                                state["selected_case_id"] = case_id
                                ui.notify(
                                    f"Expediente guardado como «{_default_draft_title()}»",
                                    type="positive",
                                )
                                navigate("detail", case_id)
                            except Exception as exc:
                                ui.notify(f"Error en la investigación: {exc}", type="negative")
                            finally:
                                ai_loading_dialog.close()
                                status_label.classes(add="hidden")
    
                        with ui.row().classes("w-full justify-end pt-2"):
                            editorial_button("EJECUTAR INVESTIGACIÓN Y TASACIÓN", on_click=run_investigation)

        with ui.column().classes("w-full py-8 gap-6"):
            with ui.row().classes("w-full justify-between items-end border-b border-[#141413] pb-3"):
                with ui.column().classes("gap-1"):
                    ui.html("<span class='micro-coord'>02 // ARCHIVO RECIENTE DE EXPEDIENTES</span>")
                    ui.html("<h2 class='text-3xl m-0'>Últimos Casos Registrados</h2>")
                with ui.row().classes("gap-3"):
                    editorial_button("VER ARCHIVO COMPLETO", on_click=lambda: navigate("library"))
                    editorial_button("LOTES COMERCIALES", on_click=lambda: navigate("lots"))

            all_cases = cloud_case_items()
            recent_cases = all_cases[-6:][::-1]

            if not recent_cases:
                ui.html("<p class='text-[#625E57] italic text-xs py-8'>No hay peritajes registrados en el sistema.</p>")
            else:
                with ui.row().classes("w-full grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"):
                    for idx, item in enumerate(recent_cases):
                        render_catalog_card(item, idx, show_delete=False)

    # ------------------------------------------
    # VISTA 2: RESULT SCREEN
    # ------------------------------------------
    def build_result_view():
        active_case = state.get("active_case_id")
        if active_case:
            state["selected_case_id"] = active_case
            build_detail_view()
        else:
            build_main_view()

    # ------------------------------------------
    # VISTA 3: LIBRARY
    # ------------------------------------------
    def build_library_view():
        render_top_bar("CH-ARCHIVE // 03")

        with ui.column().classes("w-full items-center py-5 border-b border-[#141413] mb-8"):
            ui.html("<h1 class='masthead-title text-center m-0'>CH CURIOSITIES HUNTER — ARCHIVE</h1>")
            ui.html("<p class='micro-coord mt-2'>CATÁLOGO GENERAL DE PIEZAS AUTENTICADAS Y VALORADAS</p>")

        cases = cloud_case_items()
        if not cases:
            ui.html("<p class='text-center text-[#625E57] w-full py-12'>No existen casos registrados en el sistema.</p>")
        else:
            with ui.row().classes("w-full grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"):
                for idx, item in enumerate(cases):
                    render_catalog_card(item, idx, show_delete=can_delete_in_archive())

    # ------------------------------------------
    # VISTA 4: LOTES COMERCIALES
    # ------------------------------------------
    def build_lots_view():
        render_top_bar("CH-LOTS // 04")
        pieces = _lot_pieces()
        by_id = {piece["case_id"]: piece for piece in pieces}
        lots = load_lots()

        with ui.column().classes("w-full items-center py-5 border-b border-[#141413] mb-6"):
            ui.html("<h1 class='masthead-title text-center m-0'>LOTES COMERCIALES</h1>")
            ui.html("<p class='micro-coord mt-2'>AGRUPACIÓN ESTRATÉGICA DE SALIDA POR MERCADO</p>")

        if can_manage_lots():
            with ui.expansion("CREAR NUEVO LOTE COMERCIAL", value=not bool(lots)).classes("w-full border border-[#141413] mb-6 p-2"):
                with ui.row().classes("w-full grid grid-cols-1 md:grid-cols-12 gap-4 items-end p-2"):
                    lot_name_in = ui.input(label="Nombre del lote", placeholder="Ej. Oro vintage, primavera").classes("md:col-span-7 w-full")
                    strategy_sel = ui.select(
                        list(STRATEGIES),
                        value=STRATEGIES[0],
                        label="Estrategia de salida",
                    ).classes("md:col-span-5 w-full")

                    def create_new_lot():
                        if not (lot_name_in.value or "").strip():
                            ui.notify("Escribe un nombre para el lote.", type="warning")
                        else:
                            create_lot(lot_name_in.value.strip(), strategy_sel.value, [])
                            refresh_ui()

                    editorial_button("CREAR LOTE", on_click=create_new_lot, extra_classes="mt-2")

        def render_piece_grid_ui(piece_list: list, lot_id: str, action: str):
            with ui.row().classes("w-full grid grid-cols-1 md:grid-cols-3 gap-6 my-3"):
                for idx, piece in enumerate(piece_list):
                    row = piece_contribution(piece.get("metadata") or {}, piece.get("dictamen") or "")
                    case_id = piece.get("case_id")
                    thumbnail = _piece_thumbnail(piece)
                    web_src = _media_src(thumbnail or "")
                    val_info = _extract_true_market_valuation(piece.get("dictamen") or "", piece.get("metadata") or {})
                    amount = val_info["display"]
                    maker = piece.get("maker") or str(case_id)
                    real_name = piece.get("label") or case_id

                    with ui.element("div").classes("catalog-card w-full"):
                        with ui.column().classes("w-full gap-0"):
                            if web_src:
                                ui.html(f"<div class='catalog-img-frame'><img src='{html.escape(web_src)}'/></div>")
                            else:
                                ui.html("<div class='catalog-img-frame flex items-center justify-center'><span class='micro-coord'>SIN MINIATURA</span></div>")
                            ui.html(f"<div class='catalog-roman'>{to_roman(idx)}</div>")
                            ui.html(f"<div class='catalog-brand'>{html.escape(maker)}</div>")
                            ui.html(
                                f"<div class='catalog-row'>"
                                f"<span class='catalog-title-text'>{html.escape(real_name)}</span>"
                                f"<span class='catalog-price-text'>{html.escape(amount)}</span>"
                                f"</div>"
                            )
                            ui.html(f"<p class='catalog-excerpt'>{html.escape(_piece_metrics(row))}</p>")
                        with ui.row().classes("w-full justify-between items-center pt-2"):
                            editorial_button("FICHA", on_click=lambda _, cid=case_id: navigate("detail", cid))
                            if action == "remove" and can_manage_lots():
                                def drop_member(lid=lot_id, cid=case_id):
                                    current = next((l for l in load_lots() if l.get("lot_id") == lid), None)
                                    kept = [item for item in (current or {}).get("case_ids") or [] if item != cid]
                                    update_lot_members(lid, kept)
                                    refresh_ui()
                                editorial_button("QUITAR", on_click=drop_member)
                            elif action == "add" and can_manage_lots():
                                def add_member(lid=lot_id, cid=case_id):
                                    current = next((l for l in load_lots() if l.get("lot_id") == lid), None)
                                    update_lot_members(lid, list((current or {}).get("case_ids") or []) + [cid])
                                    refresh_ui()
                                editorial_button("INCLUIR", on_click=add_member)

        for lot in lots:
            lid = lot.get("lot_id")
            report = summarize_lot(lot, pieces)
            ui.html(_lot_brief_html(report))
            if can_manage_lots():
                with ui.row().classes("w-full justify-end mb-2"):
                    def del_lot(l_id=lid):
                        delete_lot(l_id)
                        refresh_ui()
                    editorial_button("ELIMINAR LOTE", on_click=del_lot)

            members = [by_id[cid] for cid in lot.get("case_ids") or [] if cid in by_id]
            if members:
                render_piece_grid_ui(members, lid, "remove")

            member_ids = {p["case_id"] for p in members}
            available = [p for p in pieces if p["case_id"] not in member_ids]
            if available:
                ui.html("<p class='micro-coord mt-4'>AÑADIR EXPEDIENTE AL LOTE</p>")
                render_piece_grid_ui(available, lid, "add")
            ui.html("<hr class='w-full border-t border-[#141413] my-6'>")

    # ------------------------------------------
    # VISTA 5: DETAIL VIEW CON PLANO TÉCNICO CAD DINÁMICO Y REACTIVO
    # ------------------------------------------
    def build_detail_view():
        target_id = state.get("selected_case_id")
        case_metadata = get_case_view_model(target_id) if target_id else {}
        if not case_metadata:
            all_cases = cloud_case_items()
            case_item = next((c for c in all_cases if c.get("case_id") == target_id), None)
            if not case_item and all_cases:
                case_item = all_cases[-1]
            if not case_item:
                ui.label("No se ha seleccionado ningún expediente válido.")
                editorial_button("VOLVER AL PANEL", on_click=lambda: navigate("main"))
                return
            case_metadata = cloud_case_metadata(case_item.get("case_id")) or case_item

        case_id = case_metadata.get("case_id")
        ficha = relationalize_metadata(case_metadata)
        folder_path = ""

        evidence_paths = list(case_metadata.get("evidence_urls") or [])
        if not evidence_paths and case_metadata.get("image_path"):
            evidence_paths = [case_metadata["image_path"]]
        dictamen_text = renumber_markdown_headers(
            case_metadata.get("dictamen_text") or "No se ha encontrado el contenido del dictamen."
        )

        maker, real_title = _extract_product_identity_from_dictamen(dictamen_text, case_metadata)
        val_info = _extract_true_market_valuation(dictamen_text, case_metadata)
        price_banner = val_info["display"]

        base_gem = normalize_gemology_data(ficha.get("gemology_data"))
        discipline_ctx = {
            **case_metadata,
            "dictamen_text": dictamen_text,
            "gemology_data": base_gem,
            "object_name": real_title,
        }
        gem_lab_active = (
            is_jewelry_or_gemology(discipline_ctx)
            or bool(case_metadata.get("manual_jewelry_mode"))
        )
        if gem_lab_active:
            seeded_gem = _auto_seed_gemology_from_dictamen(dictamen_text, base_gem)
        else:
            seeded_gem = base_gem
            if not seeded_gem.get("_user_saved"):
                seeded_gem["applies"] = False

        xray_dialog = mount_admin_xray_dialog(expediente=discipline_ctx)

        render_top_bar(f"REF // {case_id}")

        archive_label, archive_variant = _case_archive_state(case_id)
        needs_archive = _case_needs_archive(case_id, case_metadata)

        with ui.row().classes("w-full justify-between items-end pb-5 border-b border-[#141413] gap-6"):
            with ui.column().classes("gap-1"):
                ui.html(f"<span class='micro-coord'>{html.escape(maker)} · EXPEDIENTE {html.escape(str(case_id))}</span>")
                ui.html(f"<h1 class='text-4xl md:text-5xl m-0 uppercase tracking-tight'>{html.escape(real_title)}</h1>")
                ui.html(
                    f"<span class='editorial-status-badge editorial-status-badge--{html.escape(archive_variant)}'>"
                    f"{html.escape(archive_label)}</span>"
                )

            with ui.row().classes("items-end gap-8 flex-wrap"):
                if xray_dialog:
                    ui.button(
                        "🔍 Modo Auditor",
                        on_click=xray_dialog.open,
                    ).props("outline size=sm").classes(
                        "font-mono text-[10px] tracking-wider"
                    )
                if needs_archive and can_save_expedient():

                    async def save_expediente_to_archive():
                        payload = dict(get_case_view_model(case_id) or case_metadata)
                        latest = state.get("last_dictamen")
                        if latest and state.get("selected_case_id") == case_id:
                            payload["dictamen_text"] = latest
                        payload["status"] = "active"
                        payload.setdefault("object_description", payload.get("object_description") or real_title)
                        await run.io_bound(
                            _finalize_cloud_case,
                            case_id,
                            payload,
                            payload.get("dictamen_text") or dictamen_text,
                        )
                        ui.notify("Expediente guardado en la galería", type="positive")
                        refresh_ui()

                    editorial_button(
                        "GUARDAR EXPEDIENTE EN ARCHIVO",
                        on_click=save_expediente_to_archive,
                        extra_classes="editorial-btn-primary",
                    )
                if val_info["wholesale"] != "—":
                    with ui.column().classes("items-end gap-0"):
                        ui.html("<span class='micro-coord'>LIQUIDACIÓN RÁPIDA</span>")
                        ui.html(f"<span class='editorial-serif text-xl'>{html.escape(val_info['wholesale'])}</span>")
                if val_info["auction"] != "—":
                    with ui.column().classes("items-end gap-0"):
                        ui.html("<span class='micro-coord'>SUBASTA ESPECIALIZADA</span>")
                        ui.html(f"<span class='editorial-serif text-xl'>{html.escape(val_info['auction'])}</span>")
                with ui.column().classes("items-end gap-0"):
                    ui.html("<span class='micro-coord'>VALOR MINORISTA ESTIMADO</span>")
                    ui.html(f"<span class='editorial-serif text-3xl'>{html.escape(price_banner)}</span>")

                async def export_dossier_pdf():
                    ui.notify("Maquetando dossier editorial...", type="info")
                    try:
                        allow_net = case_id not in _DRAFT_CASES
                        local_evidence = []
                        pdf_cache = os.path.join("data", "temp", "pdf", case_id)
                        for index, src in enumerate(evidence_paths):
                            if os.path.exists(src):
                                local_evidence.append(src)
                            elif allow_net:
                                path = _materialize_image(
                                    src,
                                    pdf_cache,
                                    index,
                                    case_id=case_id,
                                )
                                if path:
                                    local_evidence.append(path)
                                elif _is_remote_src(src):
                                    local_evidence.append(src)

                        case_payload = dict(case_metadata)
                        case_payload.update(
                            {
                                "case_id": case_id,
                                "title": real_title,
                                "maker": maker,
                                "dictamen_text": dictamen_text,
                                "object_description": case_metadata.get("object_description") or real_title,
                                "timestamp": float(case_metadata.get("timestamp") or 0),
                                "gemology_data": seeded_gem,
                                "cad_blueprint": case_metadata.get("cad_blueprint")
                                or _infer_cad_defaults_from_dictamen(
                                    dictamen_text,
                                    case_metadata.get("cad_blueprint") or {},
                                ),
                                "valuation": val_info,
                                "logistics_intelligence": ficha.get("logistics_intelligence") or {},
                            }
                        )

                        pdf_bytes = await run.io_bound(
                            generate_dossier_pdf,
                            case_payload,
                            local_evidence,
                            None,
                        )
                        ui.download(pdf_bytes, f"Dossier_{case_id}.pdf")
                    except Exception as e:
                        ui.notify(f"Error generando PDF: {e}", type="negative")

                editorial_button("EXPORTAR DOSSIER PDF", on_click=export_dossier_pdf)

        if can_save_expedient():
            with ui.expansion("CORREGIR NOMBRE O MARCA DEL EXPEDIENTE").classes("w-full border-b border-[#141413] py-1"):
                with ui.row().classes("w-full grid grid-cols-1 md:grid-cols-12 gap-4 items-end py-2"):
                    brand_in = ui.input(label="Marca / Casa Matriz", value=maker).classes("md:col-span-4 w-full")
                    title_in = ui.input(label="Nombre real del objeto", value=real_title).classes("md:col-span-5 w-full")

                    def save_Manual_name():
                        save_custom_identity(case_id, brand_in.value or "", title_in.value or "")
                        ui.notify("Identidad del expediente actualizada", type="positive")
                        refresh_ui()

                    with ui.row().classes("md:col-span-3 w-full justify-end"):
                        editorial_button("GUARDAR NOMBRE", on_click=save_Manual_name)

        if evidence_paths:
            with ui.column().classes("w-full py-5 border-b border-[#141413] gap-2"):
                with ui.row().classes("w-full justify-between items-center"):
                    ui.html("<span class='micro-coord'>REGISTRO FOTOGRÁFICO DE EVIDENCIAS (CLIC PARA AMPLIAR)</span>")
                    ui.html(f"<span class='micro-coord'>{len(evidence_paths)} TOMAS REGISTRADAS</span>")
                with ui.row().classes("w-full flex-wrap gap-5 mt-1"):
                    for idx, full_p in enumerate(evidence_paths):
                        w_src = _media_src(full_p)
                        fname = os.path.basename(str(full_p).split("?")[0])
                        with ui.column().classes("thumb-strip-item gap-1").on("click", lambda _, p=full_p, c=fname: open_zoom(p, c)):
                            ui.html(f"<span class='micro-coord'>IMAGE 0{idx+1}</span>")
                            ui.html(f"<div class='thumb-frame'><img src='{html.escape(w_src)}' alt='IMAGE 0{idx+1}'/></div>")

        det_alerts, _ = parse_dictamen_sections(dictamen_text)
        pending_actionable = pending_actionable_requests(case_metadata, det_alerts)
        pending_q = [rec.get("user_prompt", "") for rec in pending_actionable]
        categorized = _deduplicate_and_Categorize_dictamen(dictamen_text)
        findings = executive_findings(dictamen_text)

        ficha_rows_list = [
            ("Marca / Casa", maker),
            ("Objeto", real_title),
        ]
        disc = resolve_discipline_label(discipline_ctx)
        mats = resolve_materials_label(discipline_ctx)
        if spec_value_is_present(disc):
            ficha_rows_list.append(("Disciplina", disc))
        if spec_value_is_present(mats):
            ficha_rows_list.append(("Materiales", mats))
        for lbl, val in serial_decoding_ficha_rows(discipline_ctx):
            ficha_rows_list.append((lbl, val))
        for lbl, val in [
            ("Liquidación", val_info.get("wholesale")),
            ("Subasta", val_info.get("auction")),
            ("Mercado Minorista", val_info.get("retail")),
        ]:
            if spec_value_is_present(val):
                ficha_rows_list.append((lbl, val))
        for lbl, val in findings:
            if spec_value_is_present(val):
                ficha_rows_list.append((lbl, val))

        active_tab = state.get("detail_tab", "sintesis")

        def set_tab(t_name: str):
            state["detail_tab"] = t_name
            refresh_ui()

        with ui.row().classes("w-full border-b border-[#141413] gap-2 pt-2"):
            tabs_def = [
                ("sintesis", "I · SÍNTESIS Y DICTAMEN"),
                ("auditoria", "II · MESA DE AUDITORÍA"),
                ("gemologia", "III · GEMOLOGÍA & METALES PRECIOSOS"),
                ("mercado", "IV · TASACIÓN & BUYER SEARCH"),
                ("herramientas", "V · LOGÍSTICA & ARBITRAJE"),
                ("forense", "VI · DOSSIER TÉCNICO COMPLETO"),
            ]
            for t_key, t_label in tabs_def:
                cls = "editorial-tab editorial-tab-active" if active_tab == t_key else "editorial-tab"
                btn = ui.element("button").classes(cls)
                with btn:
                    ui.html(f"<span>{html.escape(t_label)}</span>")
                btn.on("click", lambda _, k=t_key: set_tab(k))

        with ui.column().classes("w-full py-8 gap-6"):
            if active_tab == "sintesis":
                with ui.column().classes("w-full gap-8 max-w-4xl"):
                    ui.html("<span class='micro-coord'>LECTURA PERICIAL — SIN EDICIÓN</span>")
                    ui.markdown(categorized.get("sintesis") or dictamen_text).classes(
                        "editorial-reader w-full"
                    )
                    if categorized.get("mercado"):
                        ui.html("<span class='micro-coord mt-2'>VALORACIÓN Y COINCIDENCIAS DE MERCADO</span>")
                        ui.markdown(categorized["mercado"]).classes("editorial-reader w-full")

            elif active_tab == "auditoria":
                with ui.column().classes("w-full gap-8 max-w-4xl"):
                    ui.html("<span class='micro-coord'>/// FICHA TÉCNICA</span>")
                    render_public_ficha_spec_table(ficha_rows_list)
                    render_physical_metrology_block(discipline_ctx)

                    historia_widgets: dict[str, object] = {}
                    historia_files: dict[str, tuple[str, bytes]] = {}
                    has_historial = render_resolved_requests_history(
                        discipline_ctx,
                        question_answers=ficha.get("question_answers") or {},
                        widgets_out=historia_widgets,
                        files_out=historia_files,
                    )

                    ui.html("<span class='micro-coord mt-2'>/// RESOLUCIÓN DE DUDAS ACTIVAS</span>")
                    mesa_files_mem: dict[int, tuple[str, bytes]] = {}
                    mesa_widgets: dict = {}
                    if not pending_actionable:
                        ui.html(
                            "<p class='micro-coord text-[#625E57] m-0'>"
                            "No hay peticiones pendientes del perito en este expediente.</p>"
                        )
                    else:
                        for idx, rec in enumerate(pending_actionable):
                            user_prompt = str(rec.get("user_prompt", "") or "").strip()
                            request_type = str(
                                rec.get("request_type", "verificacion_visual") or "verificacion_visual"
                            )
                            if not user_prompt:
                                continue
                            prior_answer = (ficha.get("question_answers") or {}).get(user_prompt, "")
                            with ui.column().classes("question-card w-full gap-2"):
                                ui.html(
                                    f"<p class='m-0 text-[#141413] leading-relaxed'>"
                                    f"<strong>{html.escape(to_roman(idx))}.</strong> "
                                    f"{html.escape(user_prompt)}</p>"
                                )
                                opts = _choice_options(user_prompt)
                                placeholder = (
                                    "Indique la medida en mm o gramos…"
                                    if request_type == "necesita_medida"
                                    else "Describa lo observado o aporte el dato solicitado…"
                                )
                                if opts:
                                    mesa_widgets[idx] = ui.select(
                                        opts,
                                        value=prior_answer if prior_answer in opts else "",
                                        label="Respuesta",
                                    ).classes("w-full")
                                else:
                                    mesa_widgets[idx] = ui.input(
                                        label="Respuesta",
                                        value=prior_answer or "",
                                        placeholder=placeholder,
                                    ).classes("w-full")

                                def make_mesa_up(i):
                                    async def _up(e):
                                        fname, fbytes = await _extract_upload_bytes(e)
                                        if fbytes:
                                            mesa_files_mem[i] = (fname, fbytes)
                                            ui.notify("Evidencia asociada a esta petición", type="positive")
                                    return _up

                                upload_label = (
                                    "Subir foto solicitada"
                                    if request_type == "necesita_foto"
                                    else "Foto de detalle opcional"
                                )
                                ui.upload(
                                    label=upload_label,
                                    auto_upload=True,
                                    on_upload=make_mesa_up(idx),
                                ).props("accept=.jpg,.jpeg,.png,.webp flat").classes("w-full editorial-uploader")

                    if can_save_expedient() and (mesa_widgets or historia_widgets):
                        mesa_status = ui.label("").classes("micro-coord text-[#8c6d28] hidden")

                        async def submit_mesa_master() -> None:
                            mesa_status.text = (
                                "⏳ ACTUALIZANDO EXPEDIENTE Y RECALCULANDO PERITAJE…"
                            )
                            mesa_status.classes(remove="hidden")
                            answers_dict = {i: (w.value or "") for i, w in mesa_widgets.items()}
                            historia_answers = {
                                q: (w.value or "") for q, w in historia_widgets.items()
                            }
                            updated = await run.io_bound(
                                commit_ficha_answers,
                                case_id,
                                folder_path,
                                ficha,
                                pending_q,
                                answers_dict,
                                mesa_files_mem,
                                historia_answers,
                                historia_files,
                            )
                            if str(updated).startswith("[ERR") or str(updated).startswith("Error"):
                                ui.notify(str(updated), type="negative")
                                return
                            state["last_dictamen"] = updated
                            ui.notify("Expediente actualizado y peritaje recalculado", type="positive")
                            refresh_ui()

                        ui.button(
                            "Actualizar Expediente y Recalcular",
                            on_click=submit_mesa_master,
                        ).props("color=primary").classes("w-full mt-4")
                        mesa_status
                    elif (pending_actionable or has_historial) and not can_save_expedient():
                        ui.html(
                            "<p class='micro-coord text-[#625E57] m-0'>"
                            "Resolución de dudas reservada a analistas y administradores.</p>"
                        )

            elif active_tab == "gemologia":
                jewelry_ui_state = {
                    "manual": bool(case_metadata.get("manual_jewelry_mode")),
                }
                saved_cad = _infer_cad_defaults_from_dictamen(
                    dictamen_text,
                    case_metadata.get("cad_blueprint") or {},
                )
                cad_status = ui.label("").classes("micro-coord text-[#8c6d28] hidden")
                cad_payload_holder: dict = {}

                @ui.refreshable
                def gemology_laboratory_panel() -> None:
                    is_active = (
                        is_jewelry_or_gemology(discipline_ctx)
                        or bool(jewelry_ui_state.get("manual"))
                    )
                    if not is_active:
                        render_gemology_empty_state()
                        return
                    active_gem = (
                        _auto_seed_gemology_from_dictamen(dictamen_text, seeded_gem)
                        if not seeded_gem.get("_user_saved")
                        else seeded_gem
                    )
                    with ui.column().classes("w-full gap-5 human-evidence-box"):
                        render_jewelry_cad_laboratory(
                            saved_cad=saved_cad,
                            can_save=can_save_expedient(),
                            cad_payload_holder=cad_payload_holder,
                            on_apply_cad=apply_cad_blueprint,
                        )
                        render_gemology_calculator(
                            case_id=case_id,
                            dictamen_text=dictamen_text,
                            seeded_gem=active_gem,
                            can_save=can_save_expedient(),
                            spot_prices=market_engine.get_metal_spot_prices,
                            on_persist=persist_gemology,
                            on_after_save=refresh_ui,
                        )

                async def apply_cad_blueprint() -> None:
                    build = cad_payload_holder.get("build")
                    if not callable(build):
                        ui.notify("Complete las cotas del plano técnico antes de recalcular.", type="warning")
                        return
                    cad_payload = build()
                    cad_status.text = "⏳ RECALCULANDO DICTAMEN CON PLIEGO TÉCNICO CAD EN SEGUNDO PLANO..."
                    cad_status.classes(remove="hidden")
                    updated_md = await run.io_bound(
                        save_cad_blueprint_and_recalculate,
                        case_id,
                        folder_path,
                        case_metadata,
                        cad_payload,
                    )
                    state["last_dictamen"] = updated_md
                    ui.notify("Tasación recalculada con las cotas CAD y el conteo real de piedras", type="positive")
                    refresh_ui()

                with ui.column().classes("w-full gap-6 max-w-4xl"):
                    ui.html("<span class='micro-coord'>/// GEMOLOGÍA Y METALES PRECIOSOS</span>")
                    force_switch = ui.switch("Forzar Modo Joyería / Gemología").props("dense color=grey-9")
                    force_switch.bind_value(jewelry_ui_state, "manual")

                    def sync_jewelry_override() -> None:
                        save_manual_jewelry_mode(case_id, bool(jewelry_ui_state.get("manual")))
                        case_metadata["manual_jewelry_mode"] = bool(jewelry_ui_state.get("manual"))
                        gemology_laboratory_panel.refresh()

                    force_switch.on_value_change(lambda _: sync_jewelry_override())
                    gemology_laboratory_panel()
                    cad_status

            elif active_tab == "mercado":
                mkt_status = ui.label("").classes("micro-coord text-[#8c6d28] hidden")
                with ui.row().classes("w-full justify-between items-center pb-3 border-b border-[#141413]"):
                    ui.html("<span class='micro-coord'>VALORACIÓN ECONOMÉTRICA, HIPÓTESIS DE PIEDRAS Y BUYER SEARCH</span>")

                    async def refresh_appraisal():
                        mkt_status.text = "⏳ ACTUALIZANDO TASACIÓN Y BUYER SEARCH EN SEGUNDO PLANO..."
                        mkt_status.classes(remove="hidden")
                        notes_with_rigor = (
                            ficha.get("context_notes") or ficha.get("intake_notes") or real_title
                        ) + "\n\n" + JEWELRY_RIGOR_INSTRUCTIONS
                        allow_net = case_id not in _DRAFT_CASES
                        scratch, _ = _scratch_case_folder(
                            case_id,
                            dictamen_text,
                            evidence_paths,
                            allow_network=allow_net,
                        )
                        payload = dict(get_case_view_model(case_id) or case_metadata or {})
                        result = await run.io_bound(
                            expert_council.recalculate_market_and_buyers,
                            case_id=case_id,
                            metadata=payload,
                            object_description=real_title,
                            context_notes=notes_with_rigor,
                            dictamen_text=dictamen_text,
                            case_folder=scratch,
                            legacy_agent=agent,
                        )
                        updated = result.get("dictamen_text") or ""
                        if updated and not str(updated).startswith("[ERR") and not str(updated).startswith("Error"):
                            stored = dict(get_case_view_model(case_id) or payload)
                            stored["dictamen_text"] = updated
                            if result.get("market_valuation_report"):
                                stored["market_valuation_report"] = result["market_valuation_report"]
                            if result.get("master_global_audit_trail"):
                                stored["master_global_audit_trail"] = result["master_global_audit_trail"]
                            if result.get("global_audit_trail"):
                                stored["global_audit_trail"] = result["global_audit_trail"]
                            propagate_audit_trail_to_root(stored)
                            sync_master_global_audit_trail(stored)
                            if result.get("successful_queries"):
                                stored["successful_queries"] = result["successful_queries"]
                            if case_id in _DRAFT_CASES:
                                _DRAFT_CASES[case_id] = stored
                            else:
                                await run.io_bound(
                                    _finalize_cloud_case,
                                    case_id,
                                    stored,
                                    updated,
                                    evidence_paths,
                                )
                            state["last_dictamen"] = updated
                            ui.notify("¡Tasación y estrategia de mercado actualizadas!", type="positive")
                        else:
                            ui.notify(str(updated or "No se pudo actualizar la tasación."), type="negative")
                        refresh_ui()

                    if can_save_expedient():
                        editorial_button("RECALCULAR TASACIÓN Y BUYERS", on_click=refresh_appraisal)

                ui.markdown(categorized["mercado"]).classes("editorial-reader w-full")

            elif active_tab == "herramientas":
                arb_report = case_metadata.get("logistics_arbitrage_report") or {}
                with ui.column().classes("w-full gap-6 max-w-4xl"):
                    ui.html("<span class='micro-coord'>INFORME DE ADUANAS, ARBITRAJE Y HUBS</span>")
                    render_logistics_arbitrage_report(arb_report, val_info.get("display") or "—")

            elif active_tab == "forense":
                ui.html("<span class='micro-coord'>DOSSIER PERICIAL COMPLETO (SIN DUPLICADOS, LECTURA CONTINUA)</span>")
                ui.markdown(categorized["forense"]).classes("editorial-reader w-full")

    refresh_ui()


@app.get("/health")
def health_check():
    """Endpoint público para balanceadores y HEALTHCHECK del contenedor."""
    return {"status": "ok", "service": "ch-curiosities-hunter"}


if __name__ in {"__main__", "__mp_main__"}:
    os.makedirs("data/temp", exist_ok=True)
    _env = (os.getenv("ENV") or "development").lower()
    _is_production = _env == "production"
    ui.run(
        title="CH Curiosities Hunter",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        reload=not _is_production,
        show=not _is_production,
        reconnect_timeout=180.0,
        storage_secret=os.getenv("NICEGUI_STORAGE_SECRET", "ch-curiosities-hunter-secret-key"),
    )