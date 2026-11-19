"""Inteligencia logística y de mercado para la comercialización de alta joyería."""

import hashlib
import math
import re
import unicodedata

REFERENCE_BASE_EUR = 10000.0
EU_COUNTRIES = {
    "Alemania",
    "Bélgica",
    "España",
    "Francia",
    "Italia",
    "Países Bajos",
    "Portugal",
}

# Tarifas y primas de referencia del motor. No son aranceles oficiales en vivo.
MARKET_HUBS = (
    {
        "hub": "Ginebra",
        "country": "Suiza",
        "coordinates": {"lat": 46.2044, "lng": 6.1432},
        "price_multiplier": 1.22,
        "customs_tariff_rate": 0.081,
    },
    {
        "hub": "París",
        "country": "Francia",
        "coordinates": {"lat": 48.8566, "lng": 2.3522},
        "price_multiplier": 1.18,
        "customs_tariff_rate": 0.0,
    },
    {
        "hub": "Milán",
        "country": "Italia",
        "coordinates": {"lat": 45.4642, "lng": 9.1900},
        "price_multiplier": 1.12,
        "customs_tariff_rate": 0.0,
    },
    {
        "hub": "Tokio",
        "country": "Japón",
        "coordinates": {"lat": 35.6762, "lng": 139.6503},
        "price_multiplier": 1.20,
        "customs_tariff_rate": 0.10,
    },
)

ORIGIN_GAZETTEER = {
    "Madrid": {"country": "España", "coordinates": {"lat": 40.4168, "lng": -3.7038}},
    "Barcelona": {"country": "España", "coordinates": {"lat": 41.3874, "lng": 2.1686}},
    "Valencia": {"country": "España", "coordinates": {"lat": 39.4699, "lng": -0.3763}},
    "Lisboa": {"country": "Portugal", "coordinates": {"lat": 38.7223, "lng": -9.1393}},
    "París": {"country": "Francia", "coordinates": {"lat": 48.8566, "lng": 2.3522}},
    "Milán": {"country": "Italia", "coordinates": {"lat": 45.4642, "lng": 9.1900}},
    "Roma": {"country": "Italia", "coordinates": {"lat": 41.9028, "lng": 12.4964}},
    "Ginebra": {"country": "Suiza", "coordinates": {"lat": 46.2044, "lng": 6.1432}},
    "Londres": {"country": "Reino Unido", "coordinates": {"lat": 51.5074, "lng": -0.1278}},
    "Nueva York": {"country": "Estados Unidos", "coordinates": {"lat": 40.7128, "lng": -74.0060}},
    "Tokio": {"country": "Japón", "coordinates": {"lat": 35.6762, "lng": 139.6503}},
}


CUSTOM_CITY_OPTION = "Otra ciudad…"


def fold_place_name(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.strip().casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _known_place(city: str):
    folded = fold_place_name(city)
    for name, place in ORIGIN_GAZETTEER.items():
        if fold_place_name(name) == folded:
            return name, {
                "country": place["country"],
                "coordinates": dict(place["coordinates"]),
                "price_multiplier": 1.0,
                "estimated": False,
            }
    return None


def estimate_place(city: str) -> dict:
    """Interpola coordenadas y multiplicador entre las plazas fijas cuando la ciudad no está en la matriz."""
    seed = int(hashlib.sha256(city.strip().casefold().encode()).hexdigest()[:8], 16)
    hubs = list(MARKET_HUBS)
    first = hubs[seed % len(hubs)]["coordinates"]
    second = hubs[(seed // 7) % len(hubs)]["coordinates"]
    weight = (seed % 1000) / 1000
    multipliers = [hub["price_multiplier"] for hub in hubs]
    low, high = min(multipliers), max(multipliers)
    return {
        "country": "Internacional",
        "coordinates": {
            "lat": round(first["lat"] * (1 - weight) + second["lat"] * weight, 4),
            "lng": round(first["lng"] * (1 - weight) + second["lng"] * weight, 4),
        },
        "price_multiplier": round(low + weight * (high - low), 2),
        "estimated": True,
    }


def resolve_place(city: str) -> tuple:
    cleaned = " ".join(city.strip().split())
    if not cleaned:
        raise ValueError("La ciudad no puede estar vacía.")
    known = _known_place(cleaned)
    if known:
        return known
    return cleaned, estimate_place(cleaned)


def _distance_km(origin: dict, destination: dict) -> float:
    radius = 6371.0
    lat1 = math.radians(origin["lat"])
    lat2 = math.radians(destination["lat"])
    dlat = lat2 - lat1
    dlng = math.radians(destination["lng"] - origin["lng"])
    arc = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(arc))


def _insured_transport_eur(distance_km: float, insured_value: float) -> int:
    """Tránsito asegurado proporcionado al valor de la pieza, con el mismo carril de referencia de 10.000 €."""
    value = max(float(insured_value), 0.0)
    if value <= 0 or distance_km <= 0:
        return 0
    scale = min(1.0, value / REFERENCE_BASE_EUR)
    carriage = distance_km * 0.42 * scale
    insurance = value * 0.012
    lane = min(carriage + insurance, value * 0.15)
    floor = min(140 * scale, value * 0.08)
    return int(round(max(floor, lane)))


def _customs_rate(origin_country: str, hub_country: str, nominal_rate: float) -> float:
    if origin_country == hub_country:
        return 0.0
    if origin_country in EU_COUNTRIES and hub_country in EU_COUNTRIES:
        return 0.0
    return nominal_rate


_EURO_TOKEN = re.compile(
    r"€\s*(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)|(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)\s*€",
    re.IGNORECASE,
)
_FAIR_MARKET = re.compile(r"valor justo|fair market|\bfmv\b|mercado secundario", re.IGNORECASE)
_SKIP_LINE = re.compile(r"intr[ií]nsec|melt|chatarra|/ kg|por kg|liquidaci[oó]n|reposici[oó]n|\bnos\b|retail|minorista", re.IGNORECASE)


def format_eur(value: float) -> str:
    if abs(value - round(value)) < 0.05:
        number = f"{int(round(value)):,}".replace(",", ".")
    else:
        number = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{number} €"


def _parse_euro_token(raw: str) -> float:
    text = raw.replace(" ", "").replace("\u00a0", "")
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
        return float(text)
    if "," in text:
        head, tail = text.split(",", 1)
        if len(tail) == 3 and tail.isdigit():
            return float(head + tail)
        return float(f"{head}.{tail}")
    if "." in text:
        head, tail = text.split(".", 1)
        if len(tail) == 3 and tail.isdigit():
            return float(head + tail)
    return float(text)


def _euro_amounts(line: str) -> list:
    amounts = []
    for match in _EURO_TOKEN.finditer(line):
        amounts.append(_parse_euro_token(match.group(1) or match.group(2)))
    return amounts[:2]


def _range_label(amounts: list) -> str:
    if len(amounts) >= 2:
        return f"{format_eur(amounts[0])} – {format_eur(amounts[1])}"
    return format_eur(amounts[0])


def _line_label(line: str) -> str:
    cleaned = re.sub(r"[|*_`]", " ", line)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" :-")
    euro_at = cleaned.find("€")
    if euro_at > 0:
        cleaned = cleaned[:euro_at]
    return cleaned.strip(" :-")[:90]


def extract_appraisal(dictamen: str) -> dict:
    """Punto medio de la banda de mercado del dictamen. No inventa una cifra si el expediente no la fija."""
    text = dictamen or ""
    best = None
    for line in text.splitlines():
        amounts = _euro_amounts(line)
        if not amounts or _SKIP_LINE.search(line):
            continue
        score = 3 if _FAIR_MARKET.search(line) else 1
        if best and score < best["score"]:
            continue
        best = {"score": score, "amounts": amounts, "label": _line_label(line)}
    if not best:
        return {
            "eur": None,
            "label": "",
            "range_label": "",
            "pending_weight": "PENDIENTE DE PESAJE" in text.upper(),
        }
    midpoint = round(sum(best["amounts"]) / len(best["amounts"]), 2)
    return {
        "eur": midpoint,
        "label": best["label"] or "Tasación del dictamen",
        "range_label": _range_label(best["amounts"]),
        "pending_weight": False,
    }


def _market_value(base_eur: float, multiplier: float) -> float:
    return round(float(base_eur) * float(multiplier), 2)


def _customs_eur(market_value: float, tariff_rate: float) -> float:
    return round(market_value * tariff_rate, 2)


def _net_proceeds(market_value: float, customs_eur: float, transport_eur: float) -> float:
    return round(market_value - customs_eur - transport_eur, 2)


def _price_justification(
    plaza: str,
    multiplier: float,
    appraisal_eur: float,
    market_value: float,
    tariff_rate: float,
    customs_eur: float,
    transport_eur: float,
    distance_km: int,
    local_net: float,
    same_country: bool,
    intra_eu: bool,
) -> str:
    premium = (multiplier - 1) * 100
    net = _net_proceeds(market_value, customs_eur, transport_eur)
    if abs(premium) < 0.5:
        price = f"{plaza} toma la tasación pericial sin prima de plaza y la sitúa en {format_eur(market_value)}."
    elif premium > 0:
        price = (
            f"{plaza} aplica una prima del {premium:.0f}% sobre la tasación de {format_eur(appraisal_eur)} "
            f"y sitúa el valor de mercado en {format_eur(market_value)}."
        )
    else:
        price = (
            f"{plaza} aplica un descuento del {abs(premium):.0f}% sobre la tasación de {format_eur(appraisal_eur)} "
            f"y sitúa el valor de mercado en {format_eur(market_value)}."
        )
    if tariff_rate <= 0 and same_country:
        duty = "La operación permanece en el mismo país y no devenga arancel."
    elif tariff_rate <= 0 and intra_eu:
        duty = "El tránsito intracomunitario no devenga arancel."
    elif tariff_rate <= 0:
        duty = "El tipo arancelario de referencia para esta ruta es 0%."
    else:
        duty = f"El arancel de referencia es del {tariff_rate * 100:.1f}% ({format_eur(customs_eur)})."
    if transport_eur <= 0:
        freight = "No se carga transporte asegurado porque el destino coincide con el origen."
    else:
        freight = f"El transporte asegurado son {format_eur(transport_eur)} por {distance_km:,} km.".replace(",", ".")
    delta = net - local_net
    if abs(delta) < 1:
        gap = "El neto coincide con la venta en origen."
    else:
        gap = f"El neto queda {format_eur(abs(delta))} {'por encima' if delta > 0 else 'por debajo'} de la venta en origen."
    return " ".join((price, duty, freight, gap))


def financial_rows(origin: dict, hubs: list, appraisal_eur: float) -> list:
    """Desglose de venta en origen y de cada hub a partir de la tasación de la pieza."""
    local_multiplier = float(origin.get("price_multiplier") or 1)
    local_market = _market_value(appraisal_eur, local_multiplier)
    local_net = local_market
    rows = [{
        "plaza": f"Venta en origen · {origin.get('city', '—')}",
        "market_value_eur": local_market,
        "insured_transport_eur": 0,
        "customs_eur": 0.0,
        "customs_tariff_rate": 0.0,
        "net_eur": local_net,
        "delta_vs_local_eur": 0.0,
        "justification": (
            f"Base pericial de {format_eur(appraisal_eur)}"
            + (
                f", ajustada por el multiplicador interpolado de la plaza ({local_multiplier:.2f})."
                if origin.get("estimated")
                else ", sin transporte ni arancel."
            )
        ),
    }]
    for hub in hubs:
        tariff = float(hub.get("customs_tariff_rate") or 0)
        market = _market_value(appraisal_eur, hub.get("price_multiplier") or 1)
        customs = _customs_eur(market, tariff)
        same_place = fold_place_name(str(hub.get("hub") or "")) == fold_place_name(str(origin.get("city") or ""))
        distance = float(hub.get("distance_km") or 0)
        transport = 0 if same_place else _insured_transport_eur(distance, market)
        net = _net_proceeds(market, customs, transport)
        same_country = origin.get("country") == hub.get("country")
        intra_eu = origin.get("country") in EU_COUNTRIES and hub.get("country") in EU_COUNTRIES
        rows.append({
            "plaza": hub.get("hub"),
            "market_value_eur": market,
            "insured_transport_eur": transport,
            "customs_eur": customs,
            "customs_tariff_rate": round(tariff, 4),
            "net_eur": net,
            "delta_vs_local_eur": round(net - local_net, 2),
            "justification": _price_justification(
                hub.get("hub") or "La plaza",
                float(hub.get("price_multiplier") or 1),
                appraisal_eur,
                market,
                tariff,
                customs,
                transport,
                int(hub.get("distance_km") or 0),
                local_net,
                same_country,
                intra_eu,
            ),
        })
    return rows


def logistics_brief(origin: dict, hubs: list, appraisal_eur: float) -> dict:
    """Estrategia visible. El desglose numérico queda para la auditoría y no pinta márgenes absurdos."""
    rows = financial_rows(origin, hubs, appraisal_eur)
    local = rows[0]
    exports = [row for row in rows[1:] if row.get("plaza")]
    best = max(exports, key=lambda row: row["net_eur"]) if exports else None
    appraisal_label = format_eur(appraisal_eur)
    origin_city = origin.get("city") or "origen"
    if not best:
        return {
            "strategy": "Comercialización local",
            "reason": f"Con una tasación de {appraisal_label}, la pieza se comercializa en {origin_city}.",
            "rows": rows,
        }
    delta = best["net_eur"] - local["net_eur"]
    material = max(local["net_eur"] * 0.08, 1)
    if delta >= material:
        strategy = f"Exportación a {best['plaza']}"
        reason = (
            f"Con una tasación de {appraisal_label}, {best['plaza']} aporta una prima de plaza "
            f"que cubre el tránsito y el arancel y mejora la venta en {origin_city}."
        )
    else:
        strategy = "Comercialización local"
        reason = (
            f"Con una tasación de {appraisal_label}, la prima de las plazas internacionales "
            f"no abre un margen claro sobre la venta en {origin_city}."
        )
    return {"strategy": strategy, "reason": reason, "rows": rows, "best_hub": best["plaza"]}


def build_logistics_intelligence(city: str, base_eur: float) -> dict:
    """Construye el bloque logistics_intelligence sobre la tasación real de la pieza."""
    resolved_name, place = resolve_place(city)
    origin = {
        "city": resolved_name,
        "country": place["country"],
        "coordinates": dict(place["coordinates"]),
        "estimated": place["estimated"],
        "price_multiplier": place["price_multiplier"],
    }
    appraisal = float(base_eur)
    hubs = []
    for hub in MARKET_HUBS:
        tariff = _customs_rate(origin["country"], hub["country"], hub["customs_tariff_rate"])
        distance = _distance_km(origin["coordinates"], hub["coordinates"])
        same_place = fold_place_name(hub["hub"]) == fold_place_name(resolved_name)
        market = _market_value(appraisal, hub["price_multiplier"])
        transport = 0 if same_place else _insured_transport_eur(distance, market)
        hubs.append({
            "hub": hub["hub"],
            "country": hub["country"],
            "coordinates": dict(hub["coordinates"]),
            "price_multiplier": hub["price_multiplier"],
            "customs_tariff_rate": round(tariff, 4),
            "insured_transport_eur": transport,
            "distance_km": int(round(distance)),
        })
    brief = logistics_brief(origin, hubs, appraisal)
    rows = brief["rows"]
    for hub, row in zip(hubs, rows[1:]):
        hub["market_value_eur"] = row["market_value_eur"]
        hub["customs_eur"] = row["customs_eur"]
        hub["insured_transport_eur"] = row["insured_transport_eur"]
        hub["net_eur"] = row["net_eur"]
        hub["delta_vs_local_eur"] = row["delta_vs_local_eur"]
        hub["justification"] = row["justification"]
    return {
        "origin_location": origin,
        "reference_base_eur": round(appraisal, 2),
        "local_price_multiplier": origin["price_multiplier"],
        "target_hubs": hubs,
        "financial_schedule": rows,
        "executive_recommendation": {
            "strategy": brief["strategy"],
            "reason": brief["reason"],
        },
    }
