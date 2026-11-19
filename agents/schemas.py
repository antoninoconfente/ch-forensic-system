"""Contratos estructurados del consejo forense (Pydantic v2)."""

import re
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class DimensionsMm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    length: float | None = Field(default=None, description="Largo en mm")
    width: float | None = Field(default=None, description="Ancho en mm")
    height: float | None = Field(default=None, description="Alto o espesor en mm")
    diameter: float | None = Field(default=None, description="Diámetro en mm")


class SynthesizedRubric(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
    model_config = ConfigDict(extra="forbid")

    taxonomy_key: str
    category_name: str
    primary_materials: list[str] = Field(default_factory=list)
    purity_or_grade: str = ""
    estimated_weight_or_volume: str = ""
    key_attributes: dict[str, str] = Field(default_factory=dict)
    dimensions_mm: DimensionsMm = Field(default_factory=DimensionsMm)
    authenticity_signals: list[str] = Field(default_factory=list)
    anomalies_detected: list[str] = Field(default_factory=list)
    new_protocol_insights: list[str] = Field(default_factory=list)
    confidence_score: int = Field(default=0, ge=0, le=100)
    technical_summary: str = ""

    @field_validator("taxonomy_key")
    @classmethod
    def normalize_taxonomy(cls, value: str) -> str:
        return normalize_snake_key(value)


class TaxonomyGuess(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
    model_config = ConfigDict(extra="forbid")

    source: str = ""
    title: str = ""
    price_estimate: str = ""
    similarity_or_relevance: str = ""
    notes: str = ""


class MarketValuationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estimated_value_low: str = ""
    estimated_value_high: str = ""
    recommended_acquisition_ceiling: str = ""
    currency: str = "EUR"
    demand_trend: str = ""
    internal_precedents_used: list[MarketComparable] = Field(default_factory=list)
    external_comparables: list[MarketComparable] = Field(default_factory=list)
    pricing_rationale: str = ""


class MarketRouteOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hub_city: str = ""
    buyer_profile: str = ""
    estimated_sale_price: float = 0.0
    auction_or_broker_fee_pct: float = 0.0
    shipping_insurance_cost: float = 0.0
    import_duty_vat_pct: float = 0.0
    net_proceeds_estimate: float = 0.0
    transit_notes: str = ""


class LogisticsArbitrageReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hs_code_estimate: str = ""
    hs_code_description: str = ""
    regulatory_alerts: list[str] = Field(default_factory=list)
    cites_or_restricted_materials: bool = False
    recommended_primary_hub: str = ""
    recommended_backup_hub: str = ""
    route_comparison: list[MarketRouteOption] = Field(default_factory=list)
    recommended_max_buy_price: float = 0.0
    net_margin_rationale: str = ""