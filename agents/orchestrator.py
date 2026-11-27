"""Orquestador base del consejo de expertos (roadmap 2.1)."""

from __future__ import annotations

from datetime import datetime

from agents.forensic_appraiser import UniversalForensicAgent
from agents.logistics_arbitrage import LogisticsArbitrageAgent
from agents.market_analyst import MarketIntelligenceAgent
from agents.schemas import (
    SERIAL_DECODING_FIELD_KEYS,
    ForensicReport,
    LogisticsArbitrageReport,
    MarketValuationReport,
    ResolvedRequest,
    infer_parent_domain,
    serial_decoding_dict,
)
from utils.audit_trail import propagate_audit_trail_to_root, sync_master_global_audit_trail
from utils.expedient_workflow import apply_expedient_state_transition
from utils.gemini_api import GeminiAPIError, append_api_metrics_lines
from utils.markdown_format import renumber_markdown_headers
from utils.user_notify import notify_ai_error
from src.research.ai_agent import LocalAIAgent


def _prior_resolved_entries(prior: dict | ForensicReport | None) -> list[ResolvedRequest]:
    entries: list[ResolvedRequest] = []
    if isinstance(prior, ForensicReport):
        entries = list(prior.preguntas_resueltas or [])
    elif isinstance(prior, dict):
        for item in prior.get("preguntas_resueltas") or []:
            if isinstance(item, dict):
                try:
                    entries.append(ResolvedRequest.model_validate(item))
                except Exception:
                    continue
    return entries


def merge_preguntas_resueltas(prior: dict | ForensicReport | None, report: ForensicReport) -> ForensicReport:
    """Fusiona historial de preguntas respondidas (prior + nuevas, sin perder claves previas)."""
    by_question: dict[str, ResolvedRequest] = {}
    for req in _prior_resolved_entries(prior) + list(report.preguntas_resueltas or []):
        key = str(req.pregunta_original or "").strip()
        if key:
            by_question[key] = req
    return report.model_copy(update={"preguntas_resueltas": list(by_question.values())})


def merge_forensic_historical_fields(
    prior: dict | ForensicReport | None, report: ForensicReport
) -> ForensicReport:
    report = merge_global_audit_trail(prior, report)
    return merge_preguntas_resueltas(prior, report)


def apply_user_resolutions_to_forensic_dict(
    prior_forensic: dict | None,
    pending_questions: list[str],
    answers_by_index: dict,
    files_by_index: dict | None = None,
    *,
    resolved_edits: dict[str, str] | None = None,
    resolved_files: dict[str, tuple[str, bytes]] | None = None,
) -> dict:
    """Persiste respuestas de la mesa antes del re-peritaje (respaldo si el LLM no las copia)."""
    from utils.parsers import _is_substantive_answer

    forensic = dict(prior_forensic or {})
    indexed: dict[str, dict] = {
        str(r.get("pregunta_original") or "").strip(): r
        for r in (forensic.get("preguntas_resueltas") or [])
        if isinstance(r, dict) and str(r.get("pregunta_original") or "").strip()
    }
    resolved_edits = resolved_edits or {}
    resolved_files = resolved_files or {}
    for question, answer in resolved_edits.items():
        q = str(question or "").strip()
        if not q:
            continue
        text = answer.strip() if isinstance(answer, str) else ""
        prior = indexed.get(q) or {"pregunta_original": q, "respuesta_usuario": ""}
        if _is_substantive_answer(text):
            indexed[q] = {"pregunta_original": q, "respuesta_usuario": text}
        elif text:
            indexed[q] = {"pregunta_original": q, "respuesta_usuario": text}
        elif q in indexed:
            indexed[q] = {**prior, "pregunta_original": q}
        if resolved_files.get(q) and not _is_substantive_answer(indexed[q].get("respuesta_usuario", "")):
            indexed[q]["respuesta_usuario"] = (
                "Evidencia fotográfica adjunta en mesa de auditoría."
            )
    for question, _upload in resolved_files.items():
        q = str(question or "").strip()
        if not q or q in resolved_edits:
            continue
        if q not in indexed:
            indexed[q] = {"pregunta_original": q, "respuesta_usuario": ""}
        if not _is_substantive_answer(str(indexed[q].get("respuesta_usuario") or "")):
            indexed[q]["respuesta_usuario"] = (
                "Evidencia fotográfica adjunta en mesa de auditoría."
            )
    files_by_index = files_by_index or {}
    for index, question in enumerate(pending_questions or []):
        q = str(question or "").strip()
        if not q:
            continue
        answer = answers_by_index.get(index, "")
        answer = answer.strip() if isinstance(answer, str) else ""
        if _is_substantive_answer(answer):
            indexed[q] = {"pregunta_original": q, "respuesta_usuario": answer}
        elif files_by_index.get(index):
            indexed[q] = {
                "pregunta_original": q,
                "respuesta_usuario": "Evidencia fotográfica adjunta en mesa de auditoría.",
            }
    forensic["preguntas_resueltas"] = list(indexed.values())
    return forensic


def _audit_trail_from_prior(prior, field: str = "global_audit_trail") -> list[str]:
    if prior is None:
        return []
    if hasattr(prior, field):
        raw = getattr(prior, field, None) or []
    elif isinstance(prior, dict):
        raw = prior.get(field) or []
    else:
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


def merge_global_audit_trail(prior: dict | ForensicReport | None, report: ForensicReport) -> ForensicReport:
    """Concatena la caja negra previa con entradas nuevas (sin sobrescribir historial)."""
    prior_entries = _audit_trail_from_prior(prior)
    new_entries = [str(x).strip() for x in (report.global_audit_trail or []) if str(x).strip()]
    return report.model_copy(update={"global_audit_trail": prior_entries + new_entries})


def merge_market_audit_trail(
    prior: dict | MarketValuationReport | None, report: MarketValuationReport
) -> MarketValuationReport:
    prior_entries = _audit_trail_from_prior(prior)
    new_entries = [str(x).strip() for x in (report.global_audit_trail or []) if str(x).strip()]
    return report.model_copy(update={"global_audit_trail": prior_entries + new_entries})


def merge_logistics_audit_trail(
    prior: dict | LogisticsArbitrageReport | None, report: LogisticsArbitrageReport
) -> LogisticsArbitrageReport:
    prior_entries = _audit_trail_from_prior(prior)
    new_entries = [str(x).strip() for x in (report.global_audit_trail or []) if str(x).strip()]
    return report.model_copy(update={"global_audit_trail": prior_entries + new_entries})


def _forensic_report_dict(report: ForensicReport) -> dict:
    data = report.model_dump()
    if not data.get("parent_domain"):
        try:
            from database.client import get_domain_rubric

            row = get_domain_rubric(report.taxonomy_key)
            if row and row.parent_domain:
                data["parent_domain"] = row.parent_domain
            else:
                data["parent_domain"] = infer_parent_domain(report.taxonomy_key)
        except Exception:
            data["parent_domain"] = infer_parent_domain(report.taxonomy_key)
    return data


def _council_log(step: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {step}", flush=True)


def _record_ai_failure(ai_errors: list[str], phase: str, exc: Exception) -> None:
    msg = str(exc).strip() or phase
    ai_errors.append(msg)
    notify_ai_error(msg)
    _council_log(f"[MoE] {phase} falló: {exc}")


def _forensic_serial_context(report: ForensicReport) -> str:
    """Texto estructurado para que el dictamen legacy use DATACIÓN y autenticidad por serie."""
    attrs = serial_decoding_dict(report)
    parts: list[str] = []
    for key in SERIAL_DECODING_FIELD_KEYS:
        val = (attrs.get(key) or "").strip()
        if val:
            parts.append(f"  · {key}: {val}")
    legacy_attrs = report.key_attributes or {}
    for key, val in legacy_attrs.items():
        if key in SERIAL_DECODING_FIELD_KEYS or not str(val).strip():
            continue
        if "serial" in key.casefold() or "serie" in key.casefold():
            parts.append(f"  · {key}: {val}")
    if not parts:
        summary = (report.technical_summary or "").strip()
        if "serial" in summary.casefold() or "serie" in summary.casefold():
            parts.append(f"  · technical_summary: {summary}")
        else:
            return ""
    return "[DECODIFICACIÓN DE SERIE — SALIDA AGENTE FORENSE]\n" + "\n".join(parts) + "\n"


def _forensic_serial_dictamen_appendix(report: ForensicReport) -> str:
    """Refuerzo al pie del dictamen cuando el JSON forense trae campos de serie."""
    attrs = serial_decoding_dict(report)
    raw = (attrs.get("serial_number_raw") or "").strip()
    fmt = (attrs.get("serial_format_analysis") or "").strip()
    dating = (attrs.get("serial_dating_inference") or "").strip()
    auth = (attrs.get("serial_authenticity_impact") or "").strip()
    if not any((raw, fmt, dating, auth)):
        return ""
    lines = [
        "\n\n---",
        "#### Decodificación de serie (peritaje forense)",
    ]
    if raw:
        lines.append(f"- **Número / referencia:** `{raw}`")
    if fmt:
        lines.append(f"- **Estructura:** {fmt}")
    lines.append("")
    lines.append("**DATACIÓN (lectura de serie)**")
    lines.append(dating or "Sin ventana temporal deducible solo por formato — verificar archivo de marca.")
    lines.append("")
    lines.append("**VERIFICACIÓN DE AUTENTICIDAD (coherencia del serial)**")
    lines.append(
        auth or "Indeterminado: el serial no confirma ni desmiente el relato sin tabla de numeración del fabricante."
    )
    return "\n".join(lines)


def _forensic_protocol_block(report: ForensicReport, rubric_version: int | None = None) -> str:
    dims = report.dimensions_mm
    dim_bits = []
    for label, val in (
        ("L", dims.length),
        ("A", dims.width),
        ("H", dims.height),
        ("Ø", dims.diameter),
    ):
        if val is not None:
            dim_bits.append(f"{label}={val} mm")
    dim_line = ", ".join(dim_bits) if dim_bits else "Pendiente de cotas verificadas en mano"

    attrs = "\n".join(f"  · {k}: {v}" for k, v in (report.key_attributes or {}).items()) or "  · —"
    materials = ", ".join(report.primary_materials) if report.primary_materials else "Por confirmar"
    signals = "\n".join(f"  - {s}" for s in report.authenticity_signals) or "  - —"
    anomalies = "\n".join(f"  - {a}" for a in report.anomalies_detected) or "  - Ninguna crítica"

    version_note = f" (protocolo v{rubric_version})" if rubric_version else ""
    base = (
        f"[BLOQUE FORENSE UNIVERSAL — {report.taxonomy_key}{version_note}]\n"
        f"Categoría pericial: {report.category_name}\n"
        f"Materiales primarios: {materials}\n"
        f"Pureza / grado: {report.purity_or_grade or '—'}\n"
        f"Peso / volumen estimado: {report.estimated_weight_or_volume or '—'}\n"
        f"Cotas forenses: {dim_line}\n"
        f"Atributos clave:\n{attrs}\n"
        f"Señales de autenticidad:\n{signals}\n"
        f"Anomalías:\n{anomalies}\n"
        f"Confianza forense: {report.confidence_score}%\n"
        f"Resumen técnico: {report.technical_summary}\n"
    )
    serial_ctx = _forensic_serial_context(report)
    if serial_ctx:
        base = base.rstrip() + "\n" + serial_ctx
    if report.recomendaciones:
        user_lines = "\n".join(
            f"  {i}. [{r.request_type}] {r.user_prompt}"
            for i, r in enumerate(report.recomendaciones, 1)
        )
        base = (
            base.rstrip()
            + "\n[PETICIONES AL PERITO — TEXTO PÚBLICO]\n"
            + user_lines
            + "\n"
        )
    # global_audit_trail: no se inyecta al dictamen legacy (caja negra solo admin / JSON persistido).
    return base


def _merge_cad_seed(report: ForensicReport) -> dict:
    """Semilla CAD compatible con ui/blueprints (cotas en mm, sin categorías fijas)."""
    cad: dict = {}
    dims = report.dimensions_mm
    if dims.diameter is not None:
        cad["cota_a_mm"] = str(dims.diameter)
    if dims.width is not None:
        cad["cota_b_mm"] = str(dims.width)
    if dims.height is not None:
        cad["cota_c_mm"] = str(dims.height)
    if dims.length is not None:
        cad["cota_d_mm"] = str(dims.length)

    attrs = report.key_attributes or {}
    for key, value in attrs.items():
        lower = key.casefold()
        if "peso" in lower and value:
            cad.setdefault("weight_g", str(value))
        if "gema" in lower or "piedra" in lower:
            cad.setdefault("extra_observations", str(value))

    if report.estimated_weight_or_volume and "weight_g" not in cad:
        cad.setdefault("weight_g", report.estimated_weight_or_volume)

    if report.primary_materials:
        cad.setdefault(
            "extra_observations",
            f"Materiales: {', '.join(report.primary_materials)}",
        )
    cad["forensic_taxonomy"] = report.taxonomy_key
    cad["forensic_category"] = report.category_name
    return cad


def _market_intelligence_block(report: MarketValuationReport | None) -> str:
    if report is None:
        return ""
    internals = "\n".join(
        f"  - {item.title} ({item.similarity_or_relevance}) · {item.notes[:180]}"
        for item in (report.internal_precedents_used or [])
    ) or "  - Sin precedentes internos indexados"
    externals = "\n".join(
        f"  - {item.title}: {item.price_estimate} · {item.notes[:140]}"
        for item in (report.external_comparables or [])
    ) or "  - Sin comparables externos destacados"
    return (
        "[BLOQUE INTELIGENCIA DE MERCADO — RAG GALERÍA CH]\n"
        f"Rango estimado: {report.estimated_value_low} — {report.estimated_value_high} {report.currency}\n"
        f"Techo adquisición recomendado: {report.recommended_acquisition_ceiling}\n"
        f"Tendencia de demanda: {report.demand_trend}\n"
        f"Precedentes internos (pgvector):\n{internals}\n"
        f"Comparables externos:\n{externals}\n"
        f"Razonamiento: {report.pricing_rationale}\n"
    )


def _append_market_dictamen(dictamen_text: str, report: MarketValuationReport | None) -> str:
    if report is None or str(dictamen_text).startswith("[ERR"):
        return dictamen_text
    block = (
        "\n\n---\n"
        "### 💹 INTELIGENCIA DE MERCADO (RAG + COMPARABLES)\n"
        f"- **Rango:** {report.estimated_value_low} — {report.estimated_value_high} {report.currency}\n"
        f"- **Techo adquisición:** {report.recommended_acquisition_ceiling}\n"
        f"- **Demanda:** {report.demand_trend}\n\n"
        f"{report.pricing_rationale}\n"
    )
    if report.internal_precedents_used:
        block += "\n**Precedentes internos CH:**\n"
        block += "\n".join(
            f"{i}. {c.title}: {c.similarity_or_relevance}"
            for i, c in enumerate(report.internal_precedents_used, 1)
        )
        block += "\n"
    return f"{dictamen_text.rstrip()}{block}"


def _append_forensic_dictamen(dictamen_text: str, report: ForensicReport) -> str:
    if str(dictamen_text).startswith("[ERR"):
        return dictamen_text
    block = (
        "\n\n---\n"
        "### 🔬 PERITAJE FORENSE UNIVERSAL (CONSEJO DE EXPERTOS)\n"
        f"- **Taxonomía:** {report.taxonomy_key}\n"
        f"- **Categoría:** {report.category_name}\n"
        f"- **Confianza:** {report.confidence_score}%\n\n"
        f"{report.technical_summary}\n"
    )
    if report.anomalies_detected:
        block += "\n**Anomalías detectadas:**\n"
        block += "\n".join(f"{i}. {a}" for i, a in enumerate(report.anomalies_detected, 1))
        block += "\n"
    if report.recomendaciones:
        block += "\n**Peticiones al perito:**\n"
        block += "\n".join(
            f"{i}. {r.user_prompt}" for i, r in enumerate(report.recomendaciones, 1)
        )
        block += "\n"
    block += _forensic_serial_dictamen_appendix(report)
    return f"{dictamen_text.rstrip()}{block}"


def _logistics_intelligence_block(report: LogisticsArbitrageReport | None) -> str:
    if report is None:
        return ""
    alerts = "\n".join(f"  - {a}" for a in (report.regulatory_alerts or [])) or "  - Ninguna alerta crítica"
    cites = "SÍ — revisión CITES/patrimonio" if report.cites_or_restricted_materials else "No detectada en esta fase"
    routes = "\n".join(
        (
            f"  - {r.hub_city}: venta est. {r.estimated_sale_price:.0f} EUR | "
            f"comisión {r.auction_or_broker_fee_pct:.1f}% | aranceles/IVA {r.import_duty_vat_pct:.1f}% | "
            f"transporte+seguro {r.shipping_insurance_cost:.0f} EUR | neto {r.net_proceeds_estimate:.0f} EUR"
        )
        for r in (report.route_comparison or [])
    ) or "  - Sin rutas calculadas"
    return (
        "[BLOQUE LOGÍSTICA Y ARBITRAJE INTERNACIONAL]\n"
        f"HS Code estimado: {report.hs_code_estimate} — {report.hs_code_description}\n"
        f"Alertas regulatorias:\n{alerts}\n"
        f"CITES / materiales restringidos: {cites}\n"
        f"Hub primario: {report.recommended_primary_hub} · Respaldo: {report.recommended_backup_hub}\n"
        f"Precio máximo compra recomendado: {report.recommended_max_buy_price:.2f} EUR\n"
        f"Comparativa de plazas:\n{routes}\n"
        f"Margen neto: {report.net_margin_rationale}\n"
    )


def _append_logistics_dictamen(dictamen_text: str, report: LogisticsArbitrageReport | None) -> str:
    if report is None or str(dictamen_text).startswith("[ERR"):
        return dictamen_text

    table_lines = [
        "| Plaza | Venta est. (EUR) | Comisión % | Aranceles/IVA % | Transporte+seguro | Neto (EUR) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in report.route_comparison or []:
        table_lines.append(
            f"| {row.hub_city} | {row.estimated_sale_price:.0f} | {row.auction_or_broker_fee_pct:.1f} | "
            f"{row.import_duty_vat_pct:.1f} | {row.shipping_insurance_cost:.0f} | {row.net_proceeds_estimate:.0f} |"
        )
    table = "\n".join(table_lines)
    cites_line = (
        "**⚠️ CITES / materiales restringidos:** Sí — requiere despacho especializado.\n"
        if report.cites_or_restricted_materials
        else "**CITES / materiales restringidos:** No señalados en esta fase.\n"
    )
    alerts = "\n".join(f"- {a}" for a in (report.regulatory_alerts or [])) or "- Sin alertas adicionales"
    block = (
        "\n\n---\n"
        "### 🌍 Logística, Aduanas y Arbitraje Internacional\n"
        f"- **HS Code estimado:** `{report.hs_code_estimate}` — {report.hs_code_description}\n"
        f"{cites_line}"
        f"- **Hub recomendado:** {report.recommended_primary_hub} (respaldo: {report.recommended_backup_hub})\n"
        f"- **Precio máximo de compra:** {report.recommended_max_buy_price:.2f} EUR\n\n"
        f"**Alertas regulatorias:**\n{alerts}\n\n"
        f"**Comparativa de plazas internacionales:**\n{table}\n\n"
        f"**Razonamiento de margen neto:** {report.net_margin_rationale}\n"
    )
    return f"{dictamen_text.rstrip()}{block}"


class ExpertCouncilOrchestrator:
    """Coordina el agente forense universal y el dictamen legado compatible con NiceGUI."""

    def __init__(
        self,
        forensic_agent: UniversalForensicAgent | None = None,
        legacy_agent: LocalAIAgent | None = None,
        market_agent: MarketIntelligenceAgent | None = None,
        logistics_agent: LogisticsArbitrageAgent | None = None,
    ):
        self.forensic_agent = forensic_agent or UniversalForensicAgent()
        self.legacy_agent = legacy_agent
        self.market_agent = market_agent or MarketIntelligenceAgent()
        self.logistics_agent = logistics_agent or LogisticsArbitrageAgent()

    def run_investigation(
        self,
        object_description: str,
        context_notes: str,
        image_paths: list | None,
        case_id: str,
        legacy_agent: LocalAIAgent | None = None,
        supplemental_instructions: str = "",
        prior_forensic_report: dict | None = None,
        prior_case_extras: dict | None = None,
    ) -> dict:
        agent = legacy_agent or self.legacy_agent
        if agent is None:
            return {
                "dictamen_text": "[ERR_L2_ORCHESTRATOR_NO_AGENT]: Agente legado no configurado.",
                "forensic_report": None,
                "market_valuation_report": None,
                "logistics_arbitrage_report": None,
                "draft_extras": {},
            }

        paths = list(image_paths or [])
        forensic_report: ForensicReport | None = None
        market_report: MarketValuationReport | None = None
        logistics_report: LogisticsArbitrageReport | None = None
        rubric_version: int | None = None
        successful_queries: list[str] = []
        forensic_dump = None
        market_dump = None
        logistics_dump = None
        ai_connection_errors: list[str] = []

        _council_log("[CONSEJO 1/3] Agente forense universal · protocolo y peritaje multimodal")
        try:
            forensic_report = self.forensic_agent.appraise(
                object_description,
                context_notes,
                paths,
                case_id=case_id,
            )
        except Exception as exc:
            _record_ai_failure(ai_connection_errors, "Agente forense", exc)
            forensic_report = None
        if forensic_report is not None:
            from database.client import get_domain_rubric

            row = get_domain_rubric(forensic_report.taxonomy_key)
            rubric_version = int(row.version) if row else 1

        enriched_notes = context_notes
        if forensic_report is not None:
            enriched_notes = (
                f"{context_notes}\n\n{_forensic_protocol_block(forensic_report, rubric_version)}"
            )
        if supplemental_instructions:
            enriched_notes = f"{enriched_notes}\n\n{supplemental_instructions}"

        parsed_forensic: ForensicReport | None = None
        if forensic_report is not None:
            parsed_forensic = (
                forensic_report
                if isinstance(forensic_report, ForensicReport)
                else ForensicReport.model_validate(forensic_report)
            )

        _council_log("[CONSEJO 2/3] Inteligencia de mercado · RAG galería + catálogos web")
        try:
            web_context, successful_queries = agent._execute_deep_research(
                object_description,
                enriched_notes,
                forensic_report=parsed_forensic,
            )
        except Exception as exc:
            _record_ai_failure(ai_connection_errors, "Búsqueda web comparables", exc)
            web_context = "[Búsqueda web omitida por timeout o error de conexión.]"
            successful_queries = []

        prior_extras = prior_case_extras or {}
        try:
            market_model = self.market_agent.analyze(
                parsed_forensic,
                object_description,
                context_notes,
                web_context,
                case_id,
                prior_market_report=prior_extras.get("market_valuation_report"),
            )
        except Exception as exc:
            _record_ai_failure(ai_connection_errors, "Agente de tasación", exc)
            market_model = None
        if market_model is not None:
            market_report = market_model
            if prior_extras.get("market_valuation_report"):
                market_report = merge_market_audit_trail(
                    prior_extras.get("market_valuation_report"), market_report
                )
            enriched_notes = f"{enriched_notes}\n\n{_market_intelligence_block(market_report)}"
            if web_context:
                enriched_notes = f"{enriched_notes}\n\n[CONTEXTO WEB DE MERCADO]\n{web_context}"

        _council_log("[CONSEJO 3/3] Logística, aduanas y arbitraje internacional")
        try:
            logistics_model = self.logistics_agent.analyze(
                parsed_forensic,
                market_report,
                object_description,
                context_notes,
                case_id,
            )
        except Exception as exc:
            _record_ai_failure(ai_connection_errors, "Agente logístico", exc)
            logistics_model = None
        logistics_report = logistics_model
        if prior_extras.get("logistics_arbitrage_report"):
            logistics_report = merge_logistics_audit_trail(
                prior_extras.get("logistics_arbitrage_report"), logistics_report
            )
        enriched_notes = f"{enriched_notes}\n\n{_logistics_intelligence_block(logistics_report)}"

        _council_log("[MoE] Dictamen integrado · tasación y Buyer Search (agente legado)")
        try:
            dictamen_text = agent.analyze_evidence(
                object_description=object_description,
                context_notes=enriched_notes,
                image_paths=paths,
                case_id=case_id,
                persist_case=False,
            )
        except GeminiAPIError as exc:
            _record_ai_failure(ai_connection_errors, "Dictamen integrado (Gemini)", exc)
            dictamen_text = f"[ERR_L3_GEMINI_INFERENCE_FAILED]: {exc}"
        except Exception as exc:
            _record_ai_failure(ai_connection_errors, "Dictamen integrado", exc)
            dictamen_text = f"[ERR_L3_GEMINI_INFERENCE_FAILED]: {exc}"
        if str(dictamen_text or "").startswith("[ERR"):
            notify_ai_error(str(dictamen_text))
            if str(dictamen_text) not in ai_connection_errors:
                ai_connection_errors.append(str(dictamen_text))

        if parsed_forensic is not None and prior_forensic_report:
            parsed_forensic = merge_forensic_historical_fields(prior_forensic_report, parsed_forensic)

        if parsed_forensic is not None:
            forensic_dump = _forensic_report_dict(parsed_forensic)
        elif forensic_report is not None:
            if hasattr(forensic_report, "model_dump"):
                forensic_dump = _forensic_report_dict(ForensicReport.model_validate(forensic_report))
            else:
                forensic_dump = dict(forensic_report)

        if market_report is not None:
            market_dump = market_report.model_dump()
        if logistics_report is not None:
            logistics_dump = logistics_report.model_dump()

        if parsed_forensic is not None:
            dictamen_text = _append_forensic_dictamen(dictamen_text, parsed_forensic)
        dictamen_text = _append_market_dictamen(dictamen_text, market_report)
        dictamen_text = _append_logistics_dictamen(dictamen_text, logistics_report)
        dictamen_text = renumber_markdown_headers(dictamen_text)

        draft_extras: dict = {}
        if parsed_forensic is not None:
            draft_extras = {
                "domain_taxonomy": parsed_forensic.taxonomy_key,
                "forensic_report": _forensic_report_dict(parsed_forensic),
                "cad_blueprint": _merge_cad_seed(parsed_forensic),
                "object_description_hint": parsed_forensic.category_name,
                "successful_queries": successful_queries,
            }
        if market_dump is not None:
            draft_extras["market_valuation_report"] = market_dump
        if logistics_dump is not None:
            draft_extras["logistics_arbitrage_report"] = logistics_dump
        dossier_seed = {
            "forensic_report": forensic_dump or prior_forensic_report or {},
            "market_valuation_report": market_dump or prior_extras.get("market_valuation_report") or {},
            "logistics_arbitrage_report": logistics_dump or prior_extras.get("logistics_arbitrage_report") or {},
        }
        legacy_metrics = agent.drain_api_metrics()
        if legacy_metrics:
            dossier_seed["global_audit_trail"] = append_api_metrics_lines(
                dossier_seed.get("global_audit_trail"),
                legacy_metrics,
            )
        propagate_audit_trail_to_root(dossier_seed)
        sync_master_global_audit_trail(dossier_seed)
        if dossier_seed.get("master_global_audit_trail"):
            draft_extras["master_global_audit_trail"] = dossier_seed["master_global_audit_trail"]
        if dossier_seed.get("global_audit_trail"):
            draft_extras["global_audit_trail"] = dossier_seed["global_audit_trail"]

        pipeline_meta = {
            **dossier_seed,
            "domain_taxonomy": draft_extras.get("domain_taxonomy") or "",
            "question_answers": prior_extras.get("question_answers") or {},
            "resolved_questions": prior_extras.get("resolved_questions") or [],
            "status": prior_extras.get("status") or "draft",
        }
        pipeline_meta = apply_expedient_state_transition(pipeline_meta, dictamen_text)
        draft_extras["workflow_state"] = pipeline_meta.get("workflow_state")
        if str(pipeline_meta.get("status") or "").lower() == "dictaminado":
            draft_extras["suggested_status"] = "dictaminado"

        if (case_id or "").strip() and forensic_dump:
            from database.client import sync_case_embedding_from_expedient

            try:
                sync_case_embedding_from_expedient(case_id, pipeline_meta, dictamen_text)
            except Exception as exc:
                print(f"[RAG] Indexación post-MoE omitida ({case_id}): {exc}", flush=True)

        return {
            "dictamen_text": dictamen_text,
            "forensic_report": forensic_dump,
            "market_valuation_report": market_dump,
            "logistics_arbitrage_report": logistics_dump,
            "draft_extras": draft_extras,
            "workflow_state": pipeline_meta.get("workflow_state"),
            "suggested_status": draft_extras.get("suggested_status"),
            "master_global_audit_trail": draft_extras.get("master_global_audit_trail"),
            "global_audit_trail": draft_extras.get("global_audit_trail"),
            "ai_connection_errors": ai_connection_errors,
        }

    def recalculate_market_and_buyers(
        self,
        *,
        case_id: str,
        metadata: dict,
        object_description: str,
        context_notes: str,
        dictamen_text: str,
        case_folder: str,
        legacy_agent: LocalAIAgent | None = None,
    ) -> dict:
        """Recálculo parcial: tasación MoE + dictamen buyers; preserva global_audit_trail."""
        agent = legacy_agent or self.legacy_agent
        if agent is None:
            return {
                "dictamen_text": "[ERR] Agente legado no configurado.",
                "market_valuation_report": metadata.get("market_valuation_report"),
            }

        prior_market = metadata.get("market_valuation_report") or {}
        parsed_forensic: ForensicReport | None = None
        forensic_raw = metadata.get("forensic_report") or {}
        ai_connection_errors: list[str] = []
        if isinstance(forensic_raw, dict) and forensic_raw:
            try:
                parsed_forensic = ForensicReport.model_validate(forensic_raw)
            except Exception:
                parsed_forensic = None

        try:
            web_context, successful_queries = agent._execute_deep_research(
                object_description,
                context_notes,
                forensic_report=parsed_forensic,
            )
        except Exception as exc:
            _record_ai_failure(ai_connection_errors, "Búsqueda web comparables", exc)
            web_context = "[Búsqueda web omitida por timeout o error de conexión.]"
            successful_queries = []

        try:
            market_model = self.market_agent.analyze(
                parsed_forensic,
                object_description,
                context_notes,
                web_context,
                case_id,
                prior_market_report=prior_market if prior_market else None,
            )
        except Exception as exc:
            _record_ai_failure(ai_connection_errors, "Agente de tasación", exc)
            market_model = None
        market_report: MarketValuationReport | None = market_model
        if market_report is not None and prior_market:
            market_report = merge_market_audit_trail(prior_market, market_report)

        notes_for_legacy = context_notes
        if market_report is not None:
            notes_for_legacy = f"{context_notes}\n\n{_market_intelligence_block(market_report)}"
        if web_context:
            notes_for_legacy = f"{notes_for_legacy}\n\n[CONTEXTO WEB DE MERCADO]\n{web_context}"

        try:
            updated_dictamen = agent.update_appraisal(case_folder, object_description, notes_for_legacy)
        except Exception as exc:
            _record_ai_failure(ai_connection_errors, "Recálculo dictamen legacy", exc)
            updated_dictamen = f"[ERR] {exc}"
        if market_report is not None and updated_dictamen and not str(updated_dictamen).startswith("[ERR"):
            updated_dictamen = _append_market_dictamen(updated_dictamen, market_report)
            updated_dictamen = renumber_markdown_headers(updated_dictamen)

        stored = dict(metadata)
        if market_report is not None:
            stored["market_valuation_report"] = market_report.model_dump()
            stored.setdefault("market_valuation", stored["market_valuation_report"])
        if successful_queries:
            stored["successful_queries"] = list(
                dict.fromkeys((metadata.get("successful_queries") or []) + successful_queries)
            )
        legacy_metrics = agent.drain_api_metrics()
        if legacy_metrics:
            stored["global_audit_trail"] = append_api_metrics_lines(
                stored.get("global_audit_trail"),
                legacy_metrics,
            )
        propagate_audit_trail_to_root(stored)
        sync_master_global_audit_trail(stored)

        refreshed_dictamen = updated_dictamen or dictamen_text
        stored = apply_expedient_state_transition(stored, refreshed_dictamen)
        if (case_id or "").strip() and stored.get("forensic_report"):
            from database.client import sync_case_embedding_from_expedient

            try:
                sync_case_embedding_from_expedient(case_id, stored, refreshed_dictamen)
            except Exception as exc:
                print(f"[RAG] Indexación post-recálculo omitida ({case_id}): {exc}", flush=True)

        return {
            "dictamen_text": refreshed_dictamen,
            "market_valuation_report": stored.get("market_valuation_report"),
            "workflow_state": stored.get("workflow_state"),
            "suggested_status": stored.get("status") if stored.get("workflow_state") == "DICTAMINADO" else None,
            "global_audit_trail": stored.get("global_audit_trail"),
            "master_global_audit_trail": stored.get("master_global_audit_trail"),
            "successful_queries": stored.get("successful_queries"),
            "ai_connection_errors": ai_connection_errors,
        }