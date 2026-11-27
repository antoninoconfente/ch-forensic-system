"""Agente de inteligencia de mercado con RAG sobre expedientes históricos."""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import ValidationError

from agents.council_prompts import (
    GLOBAL_AUDIT_TRAIL_JSON_HINT,
    MARKET_CASCADE_STRATEGY_DIRECTIVE,
    MARKET_FORENSIC_HYPOTHESIS_ALIGNMENT_DIRECTIVE,
    MARKET_JSON_PROSE_DIRECTIVE,
    MARKET_PRICE_ANCHOR_DIRECTIVE,
    MARKET_QUOTED_GEM_ASSETS_FORMULA_DIRECTIVE,
    MODO_AUDITOR_MARKET_DIRECTIVE,
    PRECEDENTS_NATURAL_LANGUAGE_DIRECTIVE,
    STRICT_PLAIN_TEXT_OUTPUT_DIRECTIVE,
    WEB_RAG_QUALITY_DIRECTIVE,
)
from agents.schemas import ForensicReport, MarketComparable, MarketValuationReport
from utils.gemini_api import GeminiAPIError, api_metrics_line_from_response, append_api_metrics_lines
from database.client import search_similar_cases

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _market_log(step: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {step}", flush=True)


def _resolve_gemini_api_key() -> str:
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return ""


def _strip_json_fence(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


class MarketIntelligenceAgent:
    """Combina precedentes internos (pgvector) con comparables externos."""

    def __init__(self, model_name: str = "gemini-3.8-flash"):
        self.model_name = model_name
        api_key = _resolve_gemini_api_key()
        if api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            try:
                self.client = genai.Client()
            except Exception:
                self.client = None
        self._api_metrics_buffer: list[str] = []

    def reset_api_metrics(self) -> None:
        self._api_metrics_buffer = []

    def drain_api_metrics(self) -> list[str]:
        lines = list(self._api_metrics_buffer or [])
        self._api_metrics_buffer = []
        return lines

    def analyze(
        self,
        forensic_report: ForensicReport | None,
        object_description: str,
        context_notes: str,
        web_market_context: str,
        case_id: str,
        prior_market_report: dict | None = None,
        expert_resolution_directive: str = "",
    ) -> MarketValuationReport | None:
        query = self._build_rag_query(forensic_report, object_description, context_notes)
        _market_log("[MERCADO] Consultando memoria vectorial de galería (pgvector)…")
        precedents = search_similar_cases(query, limit=3, exclude_case_id=case_id)
        if precedents:
            _market_log(f"[MERCADO] {len(precedents)} precedente(s) interno(s) recuperado(s).")
        else:
            _market_log("[MERCADO] Sin precedentes internos (galería vacía o RAG no disponible).")

        internal_seed = self._precedents_to_comparables(precedents)
        if self.client is None:
            return self._fallback_report(internal_seed, web_market_context)

        self.reset_api_metrics()
        resolution_header = ""
        if (expert_resolution_directive or "").strip():
            resolution_header = f"{expert_resolution_directive.strip()}\n\n"
        system = (
            f"{resolution_header}"
            "Eres el analista de mercado senior de Curiosities Hunter. Sintetiza valoración estructurada "
            "combinando precedentes internos reales (galería CH) y señales web externas. "
            "Devuelve SOLO JSON válido MarketValuationReport. "
            "internal_precedents_used debe basarse en los precedentes internos suministrados (source='CH_GALLERY'). "
            "external_comparables en señales web/catálogo. Si no hay precedentes internos, deja la lista vacía sin error.\n\n"
            f"{MODO_AUDITOR_MARKET_DIRECTIVE}\n\n"
            f"{MARKET_JSON_PROSE_DIRECTIVE}\n\n"
            f"{PRECEDENTS_NATURAL_LANGUAGE_DIRECTIVE}\n\n"
            f"{WEB_RAG_QUALITY_DIRECTIVE}\n\n"
            f"{MARKET_CASCADE_STRATEGY_DIRECTIVE}\n\n"
            f"{MARKET_PRICE_ANCHOR_DIRECTIVE}\n\n"
            f"{MARKET_FORENSIC_HYPOTHESIS_ALIGNMENT_DIRECTIVE}\n\n"
            f"{MARKET_QUOTED_GEM_ASSETS_FORMULA_DIRECTIVE}\n\n"
            f"{STRICT_PLAIN_TEXT_OUTPUT_DIRECTIVE}\n\n"
            f"{GLOBAL_AUDIT_TRAIL_JSON_HINT}"
        )
        precedents_prompt = self._precedents_for_prompt(precedents)
        prior_anchor = ""
        if isinstance(prior_market_report, dict) and prior_market_report:
            prior_anchor = (
                "\nBanda de valoración previa del expediente (mantener si comparables débiles):\n"
                f"- Bajo: {prior_market_report.get('estimated_value_low', '—')}\n"
                f"- Alto: {prior_market_report.get('estimated_value_high', '—')}\n"
                f"- Techo adquisición: {prior_market_report.get('recommended_acquisition_ceiling', '—')}\n"
            )
        notes_for_prompt = context_notes
        if (expert_resolution_directive or "").strip():
            notes_for_prompt = f"{expert_resolution_directive.strip()}\n\n{context_notes}"
        prompt = (
            f"Caso activo: {case_id}\n"
            f"Descripción: {object_description}\n"
            f"Notas: {notes_for_prompt}\n\n"
            f"Forense:\n{(forensic_report.model_dump_json() if forensic_report else '{}')}\n\n"
            f"Precedentes internos recuperados (usar solo para razonar; no citar IDs ni similitudes numéricas al usuario):\n"
            f"{json.dumps(precedents_prompt, ensure_ascii=False, indent=2)}\n\n"
            f"Contexto mercado web (ya filtrado; no cites buscadores ni traductores):\n"
            f"{web_market_context or '—'}\n\n"
            f"Comparables internos semilla:\n{json.dumps([c.model_dump() for c in internal_seed], ensure_ascii=False)}"
            f"{prior_anchor}"
        )

        raw = self._generate_json(system, prompt)
        if not raw:
            return self._fallback_report(internal_seed, web_market_context)
        try:
            report = MarketValuationReport.model_validate(json.loads(_strip_json_fence(raw)))
            if not report.internal_precedents_used and internal_seed:
                report = report.model_copy(update={"internal_precedents_used": internal_seed})
            if self._api_metrics_buffer:
                trail = append_api_metrics_lines(report.global_audit_trail, list(self._api_metrics_buffer))
                report = report.model_copy(update={"global_audit_trail": trail})
                self._api_metrics_buffer = []
            return report
        except ValidationError as exc:
            from utils.user_notify import notify_ai_error

            notify_ai_error(f"Validación MarketValuationReport: {exc}")
            _market_log(f"[MERCADO] Pydantic inválido: {exc}")
            return self._fallback_report(internal_seed, web_market_context)
        except json.JSONDecodeError as exc:
            _market_log(f"[MERCADO] JSON inválido: {exc}")
            return self._fallback_report(internal_seed, web_market_context)

    def _build_rag_query(
        self,
        forensic_report: ForensicReport | None,
        object_description: str,
        context_notes: str,
    ) -> str:
        lines = [object_description, context_notes]
        if forensic_report is not None:
            lines.extend(
                [
                    forensic_report.category_name,
                    forensic_report.technical_summary,
                    ", ".join(forensic_report.primary_materials),
                    forensic_report.purity_or_grade,
                ]
            )
        return "\n".join(part for part in lines if (part or "").strip())

    def _precedents_for_prompt(self, precedents: list[dict]) -> list[dict]:
        rows: list[dict] = []
        for row in precedents or []:
            summary = (row.get("summary_text") or row.get("dictamen_excerpt") or row.get("title") or "").strip()
            if not summary:
                continue
            rows.append({"summary": summary[:600]})
        return rows

    def _precedents_to_comparables(self, precedents: list[dict]) -> list[MarketComparable]:
        comparables: list[MarketComparable] = []
        for row in precedents or []:
            summary = (row.get("summary_text") or row.get("dictamen_excerpt") or "").strip()
            title = (row.get("title") or "Pieza similar en galería CH").strip()
            comparables.append(
                MarketComparable(
                    source="CH_GALLERY",
                    title=title,
                    price_estimate="Consultar banda en dictamen histórico",
                    similarity_or_relevance=(
                        "Precedente interno de referencia para esta familia de piezas."
                        if summary
                        else "Precedente interno recuperado por proximidad temática."
                    ),
                    notes=summary[:500],
                )
            )
        return comparables

    def _fallback_report(
        self,
        internal_seed: list[MarketComparable],
        web_market_context: str,
    ) -> MarketValuationReport:
        return MarketValuationReport(
            estimated_value_low="Pendiente",
            estimated_value_high="Pendiente",
            recommended_acquisition_ceiling="Pendiente",
            currency="EUR",
            demand_trend="Sin inferencia automática",
            internal_precedents_used=internal_seed,
            external_comparables=[],
            pricing_rationale=(web_market_context or "Sin síntesis LLM; usar dictamen legado.")[:1500],
        )

    def _generate_json(self, system_instruction: str, prompt: str) -> str | None:
        for attempt in range(3):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=[prompt],
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.2,
                        response_mime_type="application/json",
                    ),
                )
                metric_line = api_metrics_line_from_response(response)
                if metric_line:
                    self._api_metrics_buffer.append(metric_line)
                return (response.text or "").strip()
            except Exception as exc:
                _market_log(f"[MERCADO] Inferencia intento {attempt + 1}: {exc}")
                if attempt >= 2:
                    raise GeminiAPIError(str(exc)) from exc
                time.sleep(2 * (attempt + 1))
        return None