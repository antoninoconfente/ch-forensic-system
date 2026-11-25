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
    MARKET_JSON_PROSE_DIRECTIVE,
    MODO_AUDITOR_MARKET_DIRECTIVE,
    PRECEDENTS_NATURAL_LANGUAGE_DIRECTIVE,
)
from agents.schemas import ForensicReport, MarketComparable, MarketValuationReport
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

    def analyze(
        self,
        forensic_report: ForensicReport | None,
        object_description: str,
        context_notes: str,
        web_market_context: str,
        case_id: str,
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

        system = (
            "Eres el analista de mercado senior de Curiosities Hunter. Sintetiza valoración estructurada "
            "combinando precedentes internos reales (galería CH) y señales web externas. "
            "Devuelve SOLO JSON válido MarketValuationReport. "
            "internal_precedents_used debe basarse en los precedentes internos suministrados (source='CH_GALLERY'). "
            "external_comparables en señales web/catálogo. Si no hay precedentes internos, deja la lista vacía sin error.\n\n"
            f"{MODO_AUDITOR_MARKET_DIRECTIVE}\n\n"
            f"{MARKET_JSON_PROSE_DIRECTIVE}\n\n"
            f"{PRECEDENTS_NATURAL_LANGUAGE_DIRECTIVE}\n\n"
            f"{GLOBAL_AUDIT_TRAIL_JSON_HINT}"
        )
        precedents_prompt = self._precedents_for_prompt(precedents)
        prompt = (
            f"Caso activo: {case_id}\n"
            f"Descripción: {object_description}\n"
            f"Notas: {context_notes}\n\n"
            f"Forense:\n{(forensic_report.model_dump_json() if forensic_report else '{}')}\n\n"
            f"Precedentes internos recuperados (usar solo para razonar; no citar IDs ni similitudes numéricas al usuario):\n"
            f"{json.dumps(precedents_prompt, ensure_ascii=False, indent=2)}\n\n"
            f"Contexto mercado web:\n{web_market_context or '—'}\n\n"
            f"Comparables internos semilla:\n{json.dumps([c.model_dump() for c in internal_seed], ensure_ascii=False)}"
        )

        raw = self._generate_json(system, prompt)
        if not raw:
            return self._fallback_report(internal_seed, web_market_context)
        try:
            report = MarketValuationReport.model_validate(json.loads(_strip_json_fence(raw)))
            if not report.internal_precedents_used and internal_seed:
                report = report.model_copy(update={"internal_precedents_used": internal_seed})
            return report
        except (json.JSONDecodeError, ValidationError) as exc:
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
                return (response.text or "").strip()
            except Exception as exc:
                _market_log(f"[MERCADO] Inferencia intento {attempt + 1}: {exc}")
                time.sleep(2 * (attempt + 1))
        return None