"""Contratos estructurados del consejo forense (Pydantic v2)."""

import re
import time
import unicodedata
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Respuestas JSON del LLM: tolerar claves alucinadas sin tumbar el pipeline.
LLM_RESPONSE_CONFIG = ConfigDict(extra="ignore")

ActionableRequestType = Literal["necesita_foto", "necesita_medida", "verificacion_visual"]

SERIAL_DECODING_FIELD_KEYS: tuple[str, ...] = (
    "serial_number_raw",
    "serial_format_analysis",
    "serial_dating_inference",
    "serial_authenticity_impact",
)

_SERIAL_IMPACT_TOKENS = ("valida", "contradice", "indeterminado")


def normalize_snake_key(value: str) -> str:
    """UPPER_SNAKE_CASE ASCII sin tildes ni caracteres especiales."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.upper()
    text = re.sub(r"[^A-Z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def infer_parent_domain(taxonomy_key: str) -> str:
    parts = normalize_snake_key(taxonomy_key).split("_")
    return parts[0] if parts else normalize_snake_key(taxonomy_key)


class SerialDecoding(BaseModel):
    """Decodificación pericial obligatoria cuando la pieza tiene número de serie o referencia de fábrica."""

    model_config = LLM_RESPONSE_CONFIG

    serial_number_raw: str = Field(..., min_length=1, description="Transcripción literal del serial")
    serial_format_analysis: str = Field(..., min_length=1, description="Estructura, prefijos y longitud")
    serial_dating_inference: str = Field(..., min_length=1, description="Ventana temporal deducida con justificación")
    serial_authenticity_impact: str = Field(
        ...,
        min_length=3,
        description="Juicio valida | contradice | indeterminado con motivo",
    )

    @field_validator(
        "serial_number_raw",
        "serial_format_analysis",
        "serial_dating_inference",
        "serial_authenticity_impact",
    )
    @classmethod
    def strip_nonempty(cls, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("Campo de decodificación de serie vacío")
        return text

    @field_validator("serial_authenticity_impact")
    @classmethod
    def impact_must_state_verdict(cls, value: str) -> str:
        low = value.casefold()
        if not any(token in low for token in _SERIAL_IMPACT_TOKENS):
            raise ValueError(
                "serial_authenticity_impact debe contener valida, contradice o indeterminado y el motivo"
            )
        return value


class DimensionsMm(BaseModel):
    model_config = LLM_RESPONSE_CONFIG

    length: float | None = Field(default=None, description="Largo en mm")
    width: float | None = Field(default=None, description="Ancho en mm")
    height: float | None = Field(default=None, description="Alto o espesor en mm")
    diameter: float | None = Field(default=None, description="Diámetro en mm")


class ResolvedRequest(BaseModel):
    """Pregunta ya respondida en la Mesa de Auditoría."""

    model_config = LLM_RESPONSE_CONFIG

    pregunta_original: str = Field(description="La pregunta visual que se le hizo al usuario.")
    respuesta_usuario: str = Field(description="Lo que respondió el usuario.")

    @field_validator("pregunta_original", "respuesta_usuario")
    @classmethod
    def strip_resolved(cls, value: str) -> str:
        return str(value or "").strip()


class ExpertEvidenceEntry(BaseModel):
    """Prueba pericial aportada manualmente por el experto humano."""

    model_config = LLM_RESPONSE_CONFIG

    text_note: str = Field(..., min_length=1, description="Conclusión de laboratorio o estado actualizado.")
    image_path: str | None = Field(
        default=None,
        description="Ruta local o URL de la imagen de respaldo (test, pieza limpia).",
    )
    timestamp: float = Field(
        default_factory=time.time,
        description="Marca temporal del anexo.",
    )

    @field_validator("text_note", mode="before")
    @classmethod
    def strip_note(cls, value: str) -> str:
        return str(value or "").strip()

    @field_validator("image_path", mode="before")
    @classmethod
    def strip_image(cls, value):
        text = str(value or "").strip()
        return text or None


class ActionableRequest(BaseModel):
    """Doble cerebro: razonamiento forense interno + petición visible al usuario."""

    model_config = LLM_RESPONSE_CONFIG

    internal_reasoning: str = Field(
        description=(
            "Fase 1: Razonamiento forense técnico. Invisible para el usuario final."
        ),
    )
    user_prompt: str = Field(
        description=(
            "Fase 2: Una sola petición clara con anclaje visual (colores/formas de la foto)."
        ),
    )
    request_type: ActionableRequestType = Field(
        description="Tipo de acción solicitada al usuario.",
    )

    @field_validator("internal_reasoning", "user_prompt")
    @classmethod
    def strip_nonempty(cls, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("ActionableRequest requiere texto no vacío")
        return text


class DetectedGemstone(BaseModel):
    """Piedra estructurada detectada en peritaje forense (joyería)."""

    model_config = LLM_RESPONSE_CONFIG

    gem_type: str = Field(..., min_length=1, description="Especie o tipo (ej. Diamante, Zafiro).")
    cut: str = Field(default="", description="Talla observable (ej. Brillante, Cabujón).")
    estimated_carats: str = Field(
        default="",
        description="Quilates estimados como string legible (ej. ~0.10 ct).",
    )
    is_main_stone: bool = Field(
        default=False,
        description="True si es la gema principal de la pieza (como máximo una).",
    )

    @field_validator("gem_type", "cut", "estimated_carats", mode="before")
    @classmethod
    def strip_gem_text(cls, value):
        return str(value or "").strip()

    @field_validator("is_main_stone", mode="before")
    @classmethod
    def coerce_main_stone(cls, value):
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in ("1", "true", "yes", "sí", "si", "principal")


class SynthesizedRubric(BaseModel):
    model_config = LLM_RESPONSE_CONFIG

    taxonomy_key: str = Field(..., min_length=3, max_length=128)
    parent_domain: str = Field(..., min_length=2, max_length=64)
    display_name: str = Field(..., min_length=2, max_length=256)
    inspection_checklist: list[str] = Field(default_factory=list)
    authenticity_red_flags: list[str] = Field(default_factory=list)
    cad_measurement_guide: str = Field(default="")

    @field_validator("taxonomy_key", "parent_domain")
    @classmethod
    def normalize_keys(cls, value: str) -> str:
        return normalize_snake_key(value)


class ForensicReport(BaseModel):
    model_config = LLM_RESPONSE_CONFIG

    taxonomy_key: str
    category_name: str
    primary_materials: list[str] = Field(default_factory=list)
    purity_or_grade: str = ""
    estimated_weight_or_volume: str = ""
    has_factory_serial: bool = Field(
        default=False,
        description="True si la pieza muestra número de serie, referencia de fábrica o edición limitada legible",
    )
    serial_decoding: SerialDecoding | None = None
    key_attributes: dict[str, str] = Field(default_factory=dict)
    dimensions_mm: DimensionsMm = Field(default_factory=DimensionsMm)
    authenticity_signals: list[str] = Field(default_factory=list)
    anomalies_detected: list[str] = Field(default_factory=list)
    new_protocol_insights: list[str] = Field(default_factory=list)
    confidence_score: int = Field(default=0, ge=0, le=100)
    technical_summary: str = ""
    recomendaciones: list[ActionableRequest] = Field(
        default_factory=list,
        description="Peticiones de información adicional (doble cerebro).",
    )
    global_audit_trail: list[str] = Field(
        default_factory=list,
        description=(
            "CAJA NEGRA (Solo Admin): Registro inmutable de decisiones. Documenta aquí el impacto "
            "de cualquier dato nuevo. Ej: 'El usuario confirmó 16mm de cota Z. Impacto: Se valida Ref. "
            "11071, aumentando certeza pericial al 92% y subiendo valoración a 550€'."
        ),
    )
    preguntas_resueltas: list[ResolvedRequest] = Field(
        default_factory=list,
        description="Historial de preguntas ya respondidas.",
    )
    detected_gemstones: list[DetectedGemstone] = Field(
        default_factory=list,
        description=(
            "Lista estructurada de piedras detectadas. Cada entrada: gem_type, cut, "
            "estimated_carats, is_main_stone."
        ),
    )

    @field_validator("global_audit_trail", mode="before")
    @classmethod
    def coerce_global_audit_trail(cls, value):
        if value is None:
            return []
        if not isinstance(value, list):
            return []
        return [str(x).strip() for x in value if str(x).strip()]

    @field_validator("taxonomy_key")
    @classmethod
    def normalize_taxonomy(cls, value: str) -> str:
        return normalize_snake_key(value)

    @model_validator(mode="before")
    @classmethod
    def coerce_serial_decoding(cls, data):
        if not isinstance(data, dict):
            return data
        attrs = dict(data.get("key_attributes") or {})
        sd = data.get("serial_decoding")
        if isinstance(sd, dict):
            for key in SERIAL_DECODING_FIELD_KEYS:
                val = sd.get(key)
                if val is not None and str(val).strip():
                    attrs[key] = str(val).strip()

        has_flag = data.get("has_factory_serial")
        if has_flag is None:
            has_flag = bool(str(attrs.get("serial_number_raw") or "").strip())
        if not has_flag:
            has_flag = any(str(attrs.get(k) or "").strip() for k in SERIAL_DECODING_FIELD_KEYS[1:])
        data["has_factory_serial"] = bool(has_flag)

        if has_flag and not data.get("serial_decoding"):
            if all(str(attrs.get(k) or "").strip() for k in SERIAL_DECODING_FIELD_KEYS):
                data["serial_decoding"] = {k: str(attrs[k]).strip() for k in SERIAL_DECODING_FIELD_KEYS}
        data["key_attributes"] = attrs

        raw_recs = data.get("recomendaciones")
        if raw_recs is None:
            data["recomendaciones"] = []
        elif isinstance(raw_recs, list):
            data["recomendaciones"] = [item for item in raw_recs if isinstance(item, dict)]
        else:
            data["recomendaciones"] = []

        if data.get("global_audit_trail") is None:
            data["global_audit_trail"] = []

        raw_resolved = data.get("preguntas_resueltas")
        if raw_resolved is None:
            data["preguntas_resueltas"] = []
        elif isinstance(raw_resolved, list):
            data["preguntas_resueltas"] = [item for item in raw_resolved if isinstance(item, dict)]
        else:
            data["preguntas_resueltas"] = []

        raw_gems = data.get("detected_gemstones")
        if raw_gems is None:
            data["detected_gemstones"] = []
        elif isinstance(raw_gems, list):
            data["detected_gemstones"] = [item for item in raw_gems if isinstance(item, dict)]
        else:
            data["detected_gemstones"] = []

        return data

    @model_validator(mode="after")
    def require_serial_when_flagged(self) -> Self:
        if self.has_factory_serial and self.serial_decoding is None:
            raise ValueError(
                "has_factory_serial=true exige serial_decoding con los cuatro campos de análisis pericial"
            )
        if self.serial_decoding is not None:
            merged = dict(self.key_attributes)
            for key, val in self.serial_decoding.model_dump().items():
                merged[key] = val
            object.__setattr__(self, "key_attributes", merged)
        return self


def serial_decoding_dict(report: ForensicReport | dict) -> dict[str, str]:
    """Vista unificada de decodificación de serie (estructurada o legado en key_attributes)."""
    if isinstance(report, ForensicReport):
        if report.serial_decoding is not None:
            return report.serial_decoding.model_dump()
        data = report.key_attributes or {}
    else:
        forensic = report or {}
        sd = forensic.get("serial_decoding")
        if isinstance(sd, dict):
            return {k: str(sd.get(k) or "").strip() for k in SERIAL_DECODING_FIELD_KEYS}
        data = forensic.get("key_attributes") or {}
    return {k: str(data.get(k) or "").strip() for k in SERIAL_DECODING_FIELD_KEYS}


class TaxonomyGuess(BaseModel):
    model_config = LLM_RESPONSE_CONFIG

    taxonomy_key: str
    parent_domain: str
    display_name: str
    category_name: str = ""
    rationale: str = ""
    reuses_existing_key: bool = False

    @field_validator("taxonomy_key", "parent_domain")
    @classmethod
    def normalize_keys(cls, value: str) -> str:
        return normalize_snake_key(value)


class MarketComparable(BaseModel):
    model_config = LLM_RESPONSE_CONFIG

    source: str = ""
    title: str = ""
    price_estimate: str = ""
    similarity_or_relevance: str = ""
    notes: str = ""


class MarketValuationReport(BaseModel):
    model_config = LLM_RESPONSE_CONFIG

    estimated_value_low: str = Field(
        default="",
        description="Banda baja Mercado Secundario / FMV Escenario A (no liquidación).",
    )
    estimated_value_high: str = Field(
        default="",
        description="Banda alta Mercado Secundario / FMV Escenario A (no liquidación).",
    )
    recommended_acquisition_ceiling: str = ""
    currency: str = "EUR"
    # Alias frecuentes del LLM (también mapeados en model_validator before)
    valuation_low: str = ""
    valuation_high: str = ""
    valuation_currency: str = ""
    acquisition_ceiling: str = ""
    demand_trend: str = ""
    internal_precedents_used: list[MarketComparable] = Field(default_factory=list)
    external_comparables: list[MarketComparable] = Field(default_factory=list)
    pricing_rationale: str = ""
    global_audit_trail: list[str] = Field(
        default_factory=list,
        description="CAJA NEGRA: Documenta aquí todas tus decisiones técnicas y de mercado.",
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_llm_valuation_aliases(cls, data):
        if not isinstance(data, dict):
            return data
        pairs = (
            ("valuation_low", "estimated_value_low"),
            ("valuation_high", "estimated_value_high"),
            ("valuation_currency", "currency"),
            ("acquisition_ceiling", "recommended_acquisition_ceiling"),
        )
        for alias, canonical in pairs:
            alias_val = str(data.get(alias) or "").strip()
            canon_val = str(data.get(canonical) or "").strip()
            if alias_val and not canon_val:
                data[canonical] = alias_val
        return data

    @field_validator("global_audit_trail", mode="before")
    @classmethod
    def coerce_market_audit_trail(cls, value):
        if value is None or not isinstance(value, list):
            return []
        return [str(x).strip() for x in value if str(x).strip()]

    @field_validator("pricing_rationale", "demand_trend", mode="before")
    @classmethod
    def reject_json_blob_in_prose(cls, value):
        text = str(value or "").strip()
        if not text:
            return ""
        if text.startswith("{") or text.startswith("[") or '"user_prompt"' in text:
            return (
                "Valoración en revisión editorial: el modelo intentó devolver estructura JSON "
                "en un campo de prosa; reformule en lenguaje natural."
            )
        return text


class MarketRouteOption(BaseModel):
    model_config = LLM_RESPONSE_CONFIG

    hub_city: str = ""
    buyer_profile: str = ""
    estimated_sale_price: float = 0.0
    auction_or_broker_fee_pct: float = 0.0
    shipping_insurance_cost: float = 0.0
    import_duty_vat_pct: float = 0.0
    net_proceeds_estimate: float = 0.0
    transit_notes: str = ""


class LogisticsArbitrageReport(BaseModel):
    model_config = LLM_RESPONSE_CONFIG

    hs_code_estimate: str = ""
    hs_code_description: str = ""
    regulatory_alerts: list[str] = Field(default_factory=list)
    cites_or_restricted_materials: bool = False
    recommended_primary_hub: str = ""
    recommended_backup_hub: str = ""
    route_comparison: list[MarketRouteOption] = Field(default_factory=list)
    recommended_max_buy_price: float = 0.0
    net_margin_rationale: str = ""
    global_audit_trail: list[str] = Field(
        default_factory=list,
        description="CAJA NEGRA: Documenta aquí todas tus decisiones técnicas y de mercado.",
    )

    @field_validator("global_audit_trail", mode="before")
    @classmethod
    def coerce_logistics_audit_trail(cls, value):
        if value is None or not isinstance(value, list):
            return []
        return [str(x).strip() for x in value if str(x).strip()]