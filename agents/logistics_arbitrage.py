"""Agente logístico, aduanero y de arbitraje internacional (MoE Fase 2)."""

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
    MODO_AUDITOR_LOGISTICS_DIRECTIVE,
    STRICT_PLAIN_TEXT_OUTPUT_DIRECTIVE,
)
from agents.schemas import (
    ForensicReport,
    LogisticsArbitrageReport,
    MarketRouteOption,
    MarketValuationReport,
)
from utils.gemini_api import GeminiAPIError, api_metrics_line_from_response, append_api_metrics_lines

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

_REFERENCE_HUBS = (
    "Ginebra",
    "París",
    "Londres",
    "Hong Kong",
    "Nueva York",
    "Dubái",
)


def _logistics_log(step: str) -> None:
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


def _parse_margin_midpoint(market: MarketValuationReport | None) -> float:
    if market is None:
        return 0.0
    for raw in (market.estimated_value_high, market.estimated_value_low, market.recommended_acquisition_ceiling):
        cleaned = re.sub(r"[^\d.,]", "", str(raw or ""))
        cleaned = cleaned.replace(",", ".")
        try:
            val = float(cleaned)
            if val > 0:
                return val
        except ValueError:
            continue
    return 0.0


class LogisticsArbitrageAgent:
    """Evalúa HS, CITES, transporte asegurado y arbitraje entre plazas internacionales."""

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
        market_report: MarketValuationReport | None,
        object_description: str,
        context_notes: str,
        case_id: str,
    ) -> LogisticsArbitrageReport:
        _logistics_log("[LOGÍSTICA] Evaluando arbitraje aduanero y rutas internacionales…")

        if self.client is None:
            return self._fallback_report(forensic_report, market_report)

        self.reset_api_metrics()
        system = (
            "Eres el agente logístico, aduanero y de arbitraje internacional de Curiosities Hunter. "
            "Estima HS Code aplicable, alertas regulatorias, riesgo CITES/patrimonio, costes de transporte "
            "de alto valor asegurado y comparativa de salida en hubs internacionales. "
            "Devuelve SOLO JSON LogisticsArbitrageReport con route_comparison (lista MarketRouteOption) "
            "incluyendo como mínimo rutas evaluadas hacia: "
            + ", ".join(_REFERENCE_HUBS)
            + ". Usa valores numéricos en EUR salvo indicación. Si faltan datos, estima con prudencia y documenta en transit_notes.\n\n"
            f"{MODO_AUDITOR_LOGISTICS_DIRECTIVE}\n\n"
            f"{STRICT_PLAIN_TEXT_OUTPUT_DIRECTIVE}\n\n"
            f"{GLOBAL_AUDIT_TRAIL_JSON_HINT}"
        )
        prompt = (
            f"Caso: {case_id}\n"
            f"Objeto: {object_description}\n"
            f"Notas contexto: {context_notes}\n\n"
            f"ForensicReport:\n{(forensic_report.model_dump_json() if forensic_report else '{}')}\n\n"
            f"MarketValuationReport:\n{(market_report.model_dump_json() if market_report else '{}')}\n"
        )

        raw = self._generate_json(system, prompt)
        if not raw:
            return self._fallback_report(forensic_report, market_report)
        try:
            report = LogisticsArbitrageReport.model_validate(json.loads(_strip_json_fence(raw)))
            if not report.route_comparison:
                report = report.model_copy(
                    update={"route_comparison": self._fallback_routes(market_report)}
                )
            if self._api_metrics_buffer:
                trail = append_api_metrics_lines(report.global_audit_trail, list(self._api_metrics_buffer))
                report = report.model_copy(update={"global_audit_trail": trail})
                self._api_metrics_buffer = []
            return report
        except (json.JSONDecodeError, ValidationError) as exc:
            _logistics_log(f"[LOGÍSTICA] JSON inválido: {exc}")
            return self._fallback_report(forensic_report, market_report)

    def _fallback_routes(self, market: MarketValuationReport | None) -> list[MarketRouteOption]:
        sale = _parse_margin_midpoint(market)
        routes: list[MarketRouteOption] = []
        for hub in _REFERENCE_HUBS:
            fee = 12.0 if hub in ("Ginebra", "Nueva York") else 10.0
            duty = 8.0 if hub == "Nueva York" else 3.5
            ship = max(450.0, sale * 0.015) if sale else 650.0
            proceeds = max(0.0, sale * (1 - fee / 100 - duty / 100) - ship) if sale else 0.0
            routes.append(
                MarketRouteOption(
                    hub_city=hub,
                    buyer_profile="Coleccionista / sala internacional",
                    estimated_sale_price=sale,
                    auction_or_broker_fee_pct=fee,
                    shipping_insurance_cost=round(ship, 2),
                    import_duty_vat_pct=duty,
                    net_proceeds_estimate=round(proceeds, 2),
                    transit_notes="Estimación prudente (fallback sin LLM).",
                )
            )
        return routes

    def _fallback_report(
        self,
        forensic: ForensicReport | None,
        market: MarketValuationReport | None,
    ) -> LogisticsArbitrageReport:
        materials = ", ".join(forensic.primary_materials) if forensic else "materiales no confirmados"
        cites = any(
            token in materials.casefold()
            for token in ("marfil", "coral", "tortuga", "piel", "exótica", "madera preciosa")
        )
        routes = self._fallback_routes(market)
        best = max(routes, key=lambda r: r.net_proceeds_estimate) if routes else None
        backup = sorted(routes, key=lambda r: r.net_proceeds_estimate, reverse=True)
        return LogisticsArbitrageReport(
            hs_code_estimate="Pendiente",
            hs_code_description="Clasificación arancelaria a confirmar con despacho",
            regulatory_alerts=["Verificar documentación de exportación UE y seguro de transporte all-risk"],
            cites_or_restricted_materials=cites,
            recommended_primary_hub=best.hub_city if best else "Ginebra",
            recommended_backup_hub=backup[1].hub_city if len(backup) > 1 else "París",
            route_comparison=routes,
            recommended_max_buy_price=round(_parse_margin_midpoint(market) * 0.72, 2),
            net_margin_rationale=(
                f"Fallback seguro. Materiales declarados: {materials}. "
                "Revisar partida HS y CITES antes de movimiento transfronterizo."
            ),
        )

    def _generate_json(self, system_instruction: str, prompt: str) -> str | None:
        for attempt in range(3):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=[prompt],
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.15,
                        response_mime_type="application/json",
                    ),
                )
                metric_line = api_metrics_line_from_response(response)
                if metric_line:
                    self._api_metrics_buffer.append(metric_line)
                return (response.text or "").strip()
            except Exception as exc:
                _logistics_log(f"[LOGÍSTICA] Inferencia intento {attempt + 1}: {exc}")
                if attempt >= 2:
                    raise GeminiAPIError(str(exc)) from exc
                time.sleep(2 * (attempt + 1))
        return None