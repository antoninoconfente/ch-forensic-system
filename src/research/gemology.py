"""Gemología, perlas y desglose de valor. No modifica el motor de metales: solo lee su spot."""

GEMOLOGY_START = "<!-- gemology-block -->"
GEMOLOGY_END = "<!-- /gemology-block -->"

GEM_SPECIES = ("Diamante", "Rubí", "Zafiro", "Esmeralda", "Otra gema")
GEM_COLORS = ("D-F", "G-H", "I-J", "K-Z", "Fancy")
GEM_CLARITIES = ("FL-IF", "VVS", "VS", "SI", "I")
GEM_CUTS = ("Excelente", "Muy buena", "Buena", "Regular")
GEM_NATURES = ("Natural", "Tratada", "Rellena", "Sintética")
PEARL_NATURES = ("Natural / fina", "Cultivada")
PEARL_LUSTER = ("Alto", "Medio", "Bajo")
PEARL_NACRE = ("Grueso", "Medio", "Fino")
PEARL_SURFACE = ("Limpia", "Leve", "Marcada")
PEARL_MATCHING = ("Uniforme", "Aceptable", "Disparejo")
SETTINGS = ("Garras", "Bisel", "Carril", "Pavé", "Invisible", "Tensión", "Sin engaste")
AUTHORSHIPS = (
    "Casa de alta joyería",
    "Taller de autor",
    "Manufactura comercial",
    "Sin firma identificada",
)
METALS = ("Oro 18K", "Oro 14K", "Oro 24K", "Plata 925", "Platino 950")
SUBJECTS = ("Gema", "Perla", "Gema y perla")

# Coeficientes de referencia del motor. No son cotizaciones Rapaport en vivo.
_GEM_BASE_EUR_PER_CARAT = {
    "Diamante": 2800.0,
    "Rubí": 1800.0,
    "Zafiro": 1400.0,
    "Esmeralda": 1600.0,
    "Otra gema": 400.0,
}
_COLOR = {"D-F": 1.35, "G-H": 1.0, "I-J": 0.72, "K-Z": 0.4, "Fancy": 1.5}
_CLARITY = {"FL-IF": 1.6, "VVS": 1.25, "VS": 1.0, "SI": 0.7, "I": 0.35}
_CUT = {"Excelente": 1.15, "Muy buena": 1.0, "Buena": 0.85, "Regular": 0.65}
_GEM_NATURE = {"Natural": 1.0, "Tratada": 0.55, "Rellena": 0.3, "Sintética": 0.06}
_PEARL_UNIT = {"Natural / fina": 480.0, "Cultivada": 42.0}
_LUSTER = {"Alto": 1.4, "Medio": 1.0, "Bajo": 0.6}
_NACRE = {"Grueso": 1.35, "Medio": 1.0, "Fino": 0.55}
_SURFACE = {"Limpia": 1.25, "Leve": 1.0, "Marcada": 0.6}
_MATCHING = {"Uniforme": 1.3, "Aceptable": 1.0, "Disparejo": 0.7}
_AUTHORSHIP = {
    "Casa de alta joyería": 0.35,
    "Taller de autor": 0.18,
    "Manufactura comercial": 0.06,
    "Sin firma identificada": 0.0,
}
_SETTING_FEE = {
    "Garras": 160.0,
    "Bisel": 190.0,
    "Carril": 220.0,
    "Pavé": 280.0,
    "Invisible": 340.0,
    "Tensión": 260.0,
    "Sin engaste": 80.0,
}
_METAL_PURITY = {
    "Oro 24K": ("GOLD_EUR_PER_GRAM", 1.0),
    "Oro 18K": ("GOLD_EUR_PER_GRAM", 0.75),
    "Oro 14K": ("GOLD_EUR_PER_GRAM", 0.585),
    "Plata 925": ("SILVER_EUR_PER_GRAM", 0.925),
    "Platino 950": ("PLATINUM_EUR_PER_GRAM", 0.95),
}


def blank_gemology_data() -> dict:
    return {
        "applies": False,
        "subject": "Gema",
        "gem": {
            "species": "Diamante",
            "carat": 0.0,
            "color": "G-H",
            "clarity": "VS",
            "cut": "Muy buena",
            "nature": "Natural",
            "certified": False,
            "certificate": "",
        },
        "pearl": {
            "count": 0,
            "nature": "Cultivada",
            "luster": "Medio",
            "nacre": "Medio",
            "surface": "Leve",
            "matching": "Aceptable",
        },
        "setting": "Garras",
        "authorship": "Sin firma identificada",
        "metal": {"kind": "Oro 18K", "grams": 0.0},
        "valuation": {},
    }


def normalize_gemology_data(raw: dict | None) -> dict:
    data = blank_gemology_data()
    if not isinstance(raw, dict):
        return data
    data["applies"] = bool(raw.get("applies"))
    if raw.get("subject") in SUBJECTS:
        data["subject"] = raw["subject"]
    for key in data["gem"]:
        if key in (raw.get("gem") or {}):
            data["gem"][key] = raw["gem"][key]
    for key in data["pearl"]:
        if key in (raw.get("pearl") or {}):
            data["pearl"][key] = raw["pearl"][key]
    setting_raw = str(raw.get("setting") or "").strip()
    if setting_raw:
        data["setting"] = setting_raw
    if raw.get("authorship") in AUTHORSHIPS:
        data["authorship"] = raw["authorship"]
    metal = raw.get("metal") or {}
    if metal.get("kind") in METALS:
        data["metal"]["kind"] = metal["kind"]
    if metal.get("grams") is not None:
        data["metal"]["grams"] = metal.get("grams") or 0
    if isinstance(raw.get("valuation"), dict):
        data["valuation"] = raw["valuation"]
    return data


def _money(value: float) -> float:
    return round(float(value), 2)


def metal_value_eur(kind: str, grams: float, spot: dict) -> float | None:
    """Lee el spot ya publicado por el motor de metales. No lo recalcula."""
    if not grams or float(grams) <= 0:
        return None
    key, purity = _METAL_PURITY.get(kind, _METAL_PURITY["Oro 18K"])
    price = float((spot or {}).get(key) or 0)
    if price <= 0:
        return None
    return _money(float(grams) * purity * price)


def gem_value_eur(gem: dict) -> float:
    carat = float(gem.get("carat") or 0)
    if carat <= 0:
        return 0.0
    base = _GEM_BASE_EUR_PER_CARAT.get(gem.get("species"), 400.0)
    factor = (
        _COLOR.get(gem.get("color"), 1.0)
        * _CLARITY.get(gem.get("clarity"), 1.0)
        * _CUT.get(gem.get("cut"), 1.0)
        * _GEM_NATURE.get(gem.get("nature"), 1.0)
    )
    factor *= 1.12 if gem.get("certified") else 0.88
    return _money(base * (carat ** 1.45) * factor)


def pearl_value_eur(pearl: dict) -> float:
    count = int(pearl.get("count") or 0)
    if count <= 0:
        return 0.0
    unit = _PEARL_UNIT.get(pearl.get("nature"), 42.0)
    factor = (
        _LUSTER.get(pearl.get("luster"), 1.0)
        * _NACRE.get(pearl.get("nacre"), 1.0)
        * _SURFACE.get(pearl.get("surface"), 1.0)
        * _MATCHING.get(pearl.get("matching"), 1.0)
    )
    return _money(unit * count * factor)


def value_piece(data: dict, spot: dict) -> dict:
    """Valor de pieza = metal base + gema o perla + autoría. El engaste pondera el coste de peritaje."""
    record = normalize_gemology_data(data)
    subject = record["subject"] if record["applies"] else ""
    gem_eur = gem_value_eur(record["gem"]) if subject in ("Gema", "Gema y perla") else 0.0
    pearl_eur = pearl_value_eur(record["pearl"]) if subject in ("Perla", "Gema y perla") else 0.0
    metal_eur = metal_value_eur(record["metal"]["kind"], record["metal"]["grams"], spot)
    material = (metal_eur or 0.0) + gem_eur + pearl_eur
    rate = _AUTHORSHIP.get(record["authorship"], 0.0)
    authorship_eur = _money(material * rate)
    piece_eur = _money(material + authorship_eur)
    setting_fee = _SETTING_FEE.get(record["setting"], 160.0)
    return {
        "metal_eur": metal_eur,
        "metal_kind": record["metal"]["kind"],
        "metal_grams": float(record["metal"]["grams"] or 0),
        "gem_eur": gem_eur,
        "pearl_eur": pearl_eur,
        "authorship": record["authorship"],
        "authorship_eur": authorship_eur,
        "setting": record["setting"],
        "setting_fee_eur": setting_fee,
        "piece_eur": piece_eur,
        "metal_pending": metal_eur is None,
        "partial": metal_eur is None,
    }


def format_eur(value: float) -> str:
    if abs(value - round(value)) < 0.05:
        number = f"{int(round(value)):,}".replace(",", ".")
    else:
        number = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{number} €"


def dictamen_section(data: dict, valuation: dict) -> str:
    record = normalize_gemology_data(data)
    lines = [
        GEMOLOGY_START,
        "",
        "### Gemología, perlas y desglose de valor",
        "",
    ]
    if not record["applies"]:
        lines.append("La ficha no consigna gemas ni perlas. El valor de metal sigue en el motor de metales.")
    else:
        lines.append(f"Sujeto: {record['subject']}. Engaste: {record['setting']}. Autoría: {record['authorship']}.")
        if record["subject"] in ("Gema", "Gema y perla"):
            gem = record["gem"]
            cert = gem.get("certificate") or ("certificada" if gem.get("certified") else "sin certificación oficial")
            lines.append(
                f"Gema: {gem.get('carat') or 0} ct {gem.get('species')}, color {gem.get('color')}, "
                f"pureza {gem.get('clarity')}, talla {gem.get('cut')}, naturaleza {gem.get('nature')}, {cert}."
            )
        if record["subject"] in ("Perla", "Gema y perla"):
            pearl = record["pearl"]
            lines.append(
                f"Perlas: {pearl.get('count') or 0}, {pearl.get('nature')}, lustre {pearl.get('luster')}, "
                f"nácar {pearl.get('nacre')}, superficie {pearl.get('surface')}, matching {pearl.get('matching')}."
            )
        metal_line = (
            "Metal base: pendiente de gramaje. El spot del motor de metales no se ha aplicado."
            if valuation.get("metal_pending")
            else f"Metal base ({valuation.get('metal_kind')}, {valuation.get('metal_grams')} g): {format_eur(valuation['metal_eur'])}."
        )
        lines.extend([
            metal_line,
            f"Gema: {format_eur(valuation.get('gem_eur') or 0)}.",
            f"Perla: {format_eur(valuation.get('pearl_eur') or 0)}.",
            f"Autoría o taller: {format_eur(valuation.get('authorship_eur') or 0)}.",
            f"Valor de la pieza: {format_eur(valuation.get('piece_eur') or 0)}.",
            f"Coste de peritaje por engaste ({valuation.get('setting')}): {format_eur(valuation.get('setting_fee_eur') or 0)}.",
        ])
    lines.extend(["", GEMOLOGY_END, ""])
    return "\n".join(lines)


def upsert_dictamen(dictamen: str, section: str) -> str:
    text = dictamen or ""
    start = text.find(GEMOLOGY_START)
    end = text.find(GEMOLOGY_END)
    if start >= 0 and end > start:
        end += len(GEMOLOGY_END)
        return text[:start].rstrip() + "\n\n" + section.strip() + "\n"
    body = text.rstrip()
    if not body:
        return section.strip() + "\n"
    return body + "\n\n" + section.strip() + "\n"
