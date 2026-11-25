import json
import re

from src.research.gemology import (
    GEM_SPECIES,
    METALS,
    SUBJECTS,
    format_eur as format_gem_eur,
    normalize_gemology_data,
)
from src.research.logistics import extract_appraisal, format_eur

# ==========================================
# AUTO-ACTIVACIÓN INTELIGENTE DE GEMOLOGÍA DESDE EL DICTAMEN
# ==========================================
def _auto_seed_gemology_from_dictamen(dictamen: str, saved_gem: dict) -> dict:
    norm = normalize_gemology_data(saved_gem)
    if saved_gem and saved_gem.get("_user_saved"):
        return norm

    text = (dictamen or "").lower()
    if not text:
        return norm

    has_gems = any(w in text for w in (
        "esmeralda", "diamante", "brillante", "rubí", "rubi", "zafiro",
        "gema", "piedra", "coral", "circonita", "perla", "sortija", "alianza", "solitario", "engaste"
    ))
    if not has_gems:
        return norm

    norm["applies"] = True

    has_pearl = "perla" in text
    has_stone = any(w in text for w in ("esmeralda", "diamante", "brillante", "rubí", "zafiro", "coral", "gema", "circonita"))
    if has_pearl and has_stone and "Gema y perla" in SUBJECTS:
        norm["subject"] = "Gema y perla"
    elif has_pearl and "Perla" in SUBJECTS:
        norm["subject"] = "Perla"
    elif "Gema" in SUBJECTS:
        norm["subject"] = "Gema"

    if any(k in text for k in ("750", "18k", "18 k", "primera ley")) and "oro" in text:
        for m in METALS:
            if "18" in m or "750" in m:
                norm["metal"]["kind"] = m
                break
    elif "925" in text or "plata" in text:
        for m in METALS:
            if "plata" in m.lower() or "925" in m:
                norm["metal"]["kind"] = m
                break
    elif "platino" in text:
        for m in METALS:
            if "platino" in m.lower():
                norm["metal"]["kind"] = m
                break

    species_map = [
        ("esmeralda", "esmeralda"),
        ("diamante", "diamante"),
        ("brillante", "diamante"),
        ("rubí", "rub"),
        ("zafiro", "zafiro"),
    ]
    for kw, target in species_map:
        if kw in text:
            for sp in GEM_SPECIES:
                if target in sp.lower():
                    norm["gem"]["species"] = sp
                    break
            break

    m_grams = re.search(r"(\d{1,3}(?:[\.,]\d{1,2})?)\s*(?:g|gr|gramos)\b", text)
    if m_grams and float(norm["metal"].get("grams") or 0) == 0.0:
        try:
            g_val = float(m_grams.group(1).replace(",", "."))
            if 0.5 <= g_val <= 250.0:
                norm["metal"]["grams"] = g_val
        except Exception:
            pass

    m_ct = re.search(r"(\d{1,2}(?:[\.,]\d{1,2})?)\s*(?:ct|quilates|carats)\b", text)
    if m_ct and float(norm["gem"].get("carat") or 0) == 0.0:
        try:
            c_val = float(m_ct.group(1).replace(",", "."))
            if 0.05 <= c_val <= 50.0:
                norm["gem"]["carat"] = c_val
        except Exception:
            pass

    return norm


def _humanize_audit_question(q_text: str) -> tuple[str, str | None]:
    low = q_text.lower()
    if any(w in low for w in ("refractómetro", "refractometro", "espectrofot", "ri =", "1.57", "conductividad", "tester", "uv", "365", "chelsea", "fluorescencia")):
        recommendation = (
            "RECOMENDACIÓN DE CHECKEO: Llevar la pieza a un joyero/gemólogo con lupa 10x y tester térmico/óptico "
            "para verificar si las piedras son naturales o sintéticas, y medir sus cotas en el plano CAD superior."
        )
        human_q = (
            "¿Cuál es el resultado del checkeo de las piedras en joyería (Naturales / Sintéticas / Pendiente)?"
        )
        return human_q, recommendation

    if any(w in low for w in ("peso", "balanza", "báscula", "gramos", "masa")):
        human_q = (
            "Completa el peso en gramos y las cotas B (ancho banda) y C (espesor) en el Plano Técnico CAD."
        )
        return human_q, "MEDICIÓN FÍSICA DIRECTA: Usa báscula de precisión y regla/calibre milimetrado."

    return q_text, None


# ==========================================
# MOTOR CORREGIDO DE EXTRACCIÓN DE NOMBRES Y PRECIOS
# ==========================================
def _clean_extracted_label(raw: str) -> str:
    if not raw:
        return ""
    val = re.sub(r"[*_`#]+", "", raw).strip()
    paren_match = re.search(r"\(([^()]{4,38})\)", val)
    base = re.split(r"\s*\(|\s*\[|\s*—|\s*–", val)[0].strip(" .,:;-")
    if len(base) > 42 and paren_match:
        return paren_match.group(1).strip()
    return base


def _extract_product_identity_from_dictamen(dictamen: str, metadata: dict = None) -> tuple[str, str]:
    meta = metadata or {}
    if meta.get("custom_title"):
        custom_b = (meta.get("custom_brand") or "CH CURIOSITIES HUNTER").strip().upper()
        return custom_b, meta["custom_title"].strip()

    text = dictamen or ""
    brand = ""
    product = ""

    m_brand = re.search(
        r"(?im)^[\s\*\-\d\.]*(?:Fabricante\s*/\s*Casa\s*Matriz|Casa\s*Matriz|Marca\s*/\s*Casa|Marca|Fabricante|Maison)\s*:\s*([^\n\r]+)$",
        text
    )
    if m_brand:
        raw_b = m_brand.group(1)
        if not any(neg in raw_b.lower() for neg in (
            "no identificad", "desconocid", "sin marca", "n/a", "pendiente", "anónim",
            "negativa", "no existe", "sin atribuci", "producción comercial", "genéric", "18 k", "18k", "grabada"
        )):
            brand = _clean_extracted_label(raw_b)

    product_patterns = [
        r"(?i)Tipolog[íi]a\s+de\s+objeto\s*:\s*([^\n\r]+)",
        r"(?i)Pieza\s+Verificada\s*:\s*([^\n\r]+)",
        r"(?i)Expediente\s*:\s*([^\n\r]+)",
        r"(?i)Familia\s+Tipol[oó]gica\s*:\s*([^\n\r]+)",
        r"(?i)Modelo\s*/\s*Tipolog[íi]a\s*:\s*([^\n\r]+)",
        r"(?i)Objeto\s*:\s*([^\n\r]+)",
        r"(?i)Tipolog[íi]a\s*:\s*([^\n\r]+)",
        r"(?i)Modelo\s*:\s*([^\n\r]+)",
    ]
    for pat in product_patterns:
        m = re.search(pat, text)
        if m:
            raw_line = re.sub(r"[*_`#]+", "", m.group(1)).strip()
            if any(w in raw_line.lower() for w in ("no identificad", "desconocid", "n/a", "pendiente", "actualización")):
                continue
            cand = _clean_extracted_label(raw_line)
            if cand and len(cand) >= 4:
                product = cand
                break

    if brand and product and product.lower().startswith(brand.lower()):
        trimmed = product[len(brand):].strip(" -–—,:.")
        if len(trimmed) >= 4:
            product = trimmed

    if not product:
        product = "Pieza en Auditoría"

    if len(product) > 42:
        product = product[:40].rstrip() + "…"

    maker_header = brand.upper() if brand else "CH CURIOSITIES HUNTER"
    if len(maker_header) > 30:
        maker_header = maker_header[:28].rstrip() + "…"

    return maker_header, product


def _extract_true_market_valuation(dictamen: str, metadata: dict = None) -> dict:
    meta = metadata or {}
    text = dictamen or ""

    gem_data = meta.get("gemology_data") or {}
    gem_val = (gem_data.get("valuation") or {}).get("piece_eur")
    if gem_data.get("_user_saved") and gem_data.get("applies") and gem_val:
        return {
            "display": format_gem_eur(gem_val),
            "mid_eur": float(gem_val),
            "wholesale": "—",
            "auction": "—",
            "retail": format_gem_eur(gem_val),
        }

    def _find_band(keywords: str):
        pat = rf"(?is)(?:{keywords})[^\n\|]*\|?\s*€?\s*(\d{{2,6}}(?:[\.,]\d{{3}})?)\s*€?\s*[-–—a]\s*€?\s*(\d{{2,6}}(?:[\.,]\d{{3}})?)\s*€?"
        matches = list(re.finditer(pat, text))
        if matches:
            m = matches[-1]
            low = float(m.group(1).replace(".", "").replace(",", "."))
            high = float(m.group(2).replace(".", "").replace(",", "."))
            if low >= 25 and high >= low:
                return low, high, f"{int(low):,} € – {int(high):,} €".replace(",", ".")
        return None

    retail_band = _find_band(r"Mercado\s+Secundario\s+Minorista|Fair\s+Market\s+Value|Venta\s+Curada\s+Minorista|Boutique\s*/\s*Retail|Hip[oó]tesis\s+A|Escenario\s+A")
    auction_band = _find_band(r"Subasta\s+Especializada|Banda\s+de\s+Martillo|Auction\s+Estimate|Mercado\s+Secundario\s*/\s*Subasta")
    wholesale_band = _find_band(r"Liquidaci[oó]n\s+Inmediata|Liquidaci[oó]n\s+R[aá]pida|Wholesale|Comercio\s+Mayorista|Melt\s*/\s*Fundici[oó]n")

    chosen = retail_band or auction_band or wholesale_band
    if chosen:
        low, high, label = chosen
        mid = round((low + high) / 2.0, 2)
        return {
            "display": label,
            "mid_eur": mid,
            "wholesale": wholesale_band[2] if wholesale_band else "—",
            "auction": auction_band[2] if auction_band else "—",
            "retail": retail_band[2] if retail_band else label,
        }

    appr = extract_appraisal(text)
    if appr.get("eur") and appr["eur"] > 35:
        return {
            "display": appr.get("range_label") or format_eur(appr["eur"]),
            "mid_eur": float(appr["eur"]),
            "wholesale": "—",
            "auction": "—",
            "retail": appr.get("range_label") or format_eur(appr["eur"]),
        }

    return {
        "display": "EN EVALUACIÓN",
        "mid_eur": None,
        "wholesale": "—",
        "auction": "—",
        "retail": "—",
    }


def _clean_latex_and_emojis(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"[⚠️📌🔬⚖️💎🏛️💰📊🧭🛡️✨⏳⚡💬🔄🎯]", "", text)
    cleaned = re.sub(r"\$\$[^\$]+\$\$", "", cleaned)
    cleaned = re.sub(r"\\text\{([^}]*)\}", r"\1", cleaned)
    cleaned = cleaned.replace("\\times", "×").replace("\\approx", "≈").replace("\\cdot", "·")
    cleaned = re.sub(r"\$([^\$]+)\$", r"\1", cleaned)
    return cleaned.strip()


def _deduplicate_and_Categorize_dictamen(raw_dictamen: str) -> dict:
    if not raw_dictamen:
        return {"sintesis": "", "mercado": "", "forense": ""}

    _, body = parse_dictamen_sections(raw_dictamen)
    cleaned = _clean_latex_and_emojis(body)

    reeval_pattern = re.compile(
        r"(?m)^(?:#{1,4}\s*)?[^\n]*(?:REEVALUACI[OÓ]N\s+DIN[AÁ]MICA|ACTUALIZACI[OÓ]N\s+DEL\s+M[OÓ]DULO\s+DE\s+TASACI[OÓ]N)[^\n]*$"
    )
    reeval_matches = list(reeval_pattern.finditer(cleaned))
    if len(reeval_matches) >= 2:
        first_start = reeval_matches[0].start()
        last_start = reeval_matches[-1].start()
        base_doc = cleaned[:first_start].strip()
        latest_reeval = cleaned[last_start:].strip()
        cleaned = base_doc + "\n\n---\n\n" + latest_reeval

    top_header_pattern = re.compile(
        r"(?m)^(?:"
        r"#{1,3}\s+(?:\d+[\.\)]\s+)?(?=[A-ZÁÉÍÓÚÑ0-9])|"
        r"(?:\d+[\.\)]\s+)(?=(?:ALERTAS|IDENTIFICACI[OÓ]N|AN[AÁ]LISIS|COINCIDENCIAS|VERIFICACI[OÓ]N|DICTAMEN|VALORACI[OÓ]N|TASACI[OÓ]N|M[OÓ]DULO\s+DE\s+TASACI[OÓ]N|ESTRATEGIA\s+DE\s+BUYER|BUYER\s+SEARCH|REEVALUACI[OÓ]N))|"
        r"(?:REEVALUACI[OÓ]N\s+DIN[AÁ]MICA|COINCIDENCIAS\s+DE\s+GOOGLE|VERIFICACI[OÓ]N\s+DE\s+AUTENTICIDAD|DICTAMEN\s+PERICIAL\s+FINAL|ESTRATEGIA\s+REFORZADA\s+DE\s+BUYER)"
        r")[^\n]*$"
    )

    matches = list(top_header_pattern.finditer(cleaned))
    if not matches:
        return {"sintesis": cleaned, "mercado": cleaned, "forense": cleaned}

    sintesis_parts = []
    mercado_parts = []
    forense_parts = []

    in_market_zone = False

    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(cleaned)
        chunk = cleaned[start:end].strip()
        header_upper = m.group(0).upper()

        if any(k in header_upper for k in (
            "TASACIÓN", "VALORACIÓN", "MERCADO", "BUYER", "COMERCIALIZACIÓN",
            "REEVALUACIÓN", "COLOCACIÓN", "CANALES", "ARQUETIPOS"
        )):
            in_market_zone = True
            mercado_parts.append(chunk)
            continue

        if any(k in header_upper for k in (
            "IDENTIFICACIÓN FORMAL", "COINCIDENCIAS", "VERIFICACIÓN DE AUTENTICIDAD",
            "DICTAMEN PERICIAL FINAL", "AUTENTICIDAD Y PATRONES"
        )):
            in_market_zone = False
            sintesis_parts.append(chunk)
        elif in_market_zone and not any(k in header_upper for k in ("ANÁLISIS TÉCNICO", "METALURGIA", "ESTADO FÍSICO")):
            mercado_parts.append(chunk)
        else:
            in_market_zone = False
            forense_parts.append(chunk)

    return {
        "sintesis": "\n\n---\n\n".join(sintesis_parts) or cleaned,
        "mercado": "\n\n---\n\n".join(mercado_parts) or cleaned,
        "forense": cleaned,
    }

# ==========================================
# FUNCIONES AUXILIARES DE LÓGICA Y PARSEO (INTACTAS)
# ==========================================
def parse_dictamen_sections(raw_dictamen: str) -> tuple[str, str]:
    if not raw_dictamen:
        return "", ""
    alert_header = "1. ⚠️ ALERTAS DE EXCEPCIÓN Y AUDITORÍA PERICIAL"
    if alert_header in raw_dictamen:
        parts = raw_dictamen.split("2. 📌 IDENTIFICACIÓN FORMAL")
        alerts_part = parts[0].replace(alert_header, "").strip()
        rest_part = "2. 📌 IDENTIFICACIÓN FORMAL" + parts[1] if len(parts) > 1 else raw_dictamen
        return alerts_part, rest_part
    return "", raw_dictamen


def _question_identifier(text: str) -> str:
    if not text:
        return ""
    raw = str(text).strip()
    numbered = re.match(r"^(\d+)[\.\)\:]\s+", raw)
    if numbered:
        return numbered.group(1)
    labeled = re.search(r"(?i)\b(?:pregunta|cuesti[oó]n|q)\s*[:#\-]?\s*(\d+)\b", raw)
    if labeled:
        return labeled.group(1)
    return ""


def _normalize_question_text(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"\[[^\[\]]*\]", "", str(text))
    cleaned = re.sub(r"[*_`#]+", " ", cleaned)
    cleaned = re.sub(r"(?i)^(pregunta|cuesti[oó]n)(?:\s+pendiente)?\s*\d+\s*[:.\-]\s*", "", cleaned.strip())
    cleaned = re.sub(r"^(\d+[\.\)\:]|[-*•])\s+", "", cleaned)
    cleaned = cleaned.lower()
    cleaned = re.sub(r"[^\wáéíóúüñ¿?\s]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _question_is_resolved(question: str, resolved_questions: list) -> bool:
    q_id = _question_identifier(question)
    q_norm = _normalize_question_text(question)
    if not q_norm:
        return False
    q_core = q_norm[:80]
    for resolved in resolved_questions or []:
        res_id = _question_identifier(resolved)
        res_norm = _normalize_question_text(resolved)
        if not res_norm:
            continue
        if q_id and res_id and q_id == res_id:
            q_tokens = set(w for w in q_norm.split() if len(w) > 3)
            r_tokens = set(w for w in res_norm.split() if len(w) > 3)
            if q_tokens and r_tokens and (q_tokens & r_tokens):
                return True
        if q_norm == res_norm or q_norm in res_norm or res_norm in q_norm:
            return True
        if len(q_core) >= 24 and q_core in res_norm:
            return True
        res_core = res_norm[:80]
        if len(res_core) >= 24 and res_core in q_norm:
            return True
    return False


def extract_questions_from_alerts(alerts_text: str, resolved_questions: list = None) -> list:
    if not alerts_text:
        return []
    questions = []
    resolved = resolved_questions or []

    for line in alerts_text.split("\n"):
        line_s = line.strip()
        numbered = re.match(r"^(\d+[\.\)\:]|[-*•])\s+", line_s)
        if not (numbered or "?" in line_s):
            continue
        q_id = _question_identifier(line_s)
        clean_q = re.sub(r"^(\d+[\.\)\:]|[-*•])\s+", "", line_s).strip()
        if not clean_q or len(clean_q) <= 8:
            continue
        if clean_q.startswith("###") or clean_q.startswith("⚠️"):
            continue
        if _question_is_resolved(line_s, resolved) or _question_is_resolved(clean_q, resolved):
            continue
        stored = f"{q_id}. {clean_q}" if q_id else clean_q
        if stored not in questions and clean_q not in questions:
            questions.append(stored)

    return questions


_PLACEHOLDER_ANSWERS = {"", "pendiente", "n/a", "na", "—", "-", "sin respuesta"}


def _is_substantive_answer(value: str) -> bool:
    return str(value or "").strip().lower() not in _PLACEHOLDER_ANSWERS


def executive_findings(dictamen: str) -> list:
    text = re.sub(r"[*_`>#]", " ", dictamen or "")
    text = re.sub(r"\s+", " ", text).strip()
    findings = []
    has_750 = re.search(r"\b750\b", text) is not None
    has_18k = re.search(r"18\s?K", text, re.IGNORECASE) is not None
    has_925 = re.search(r"\b925\b", text) is not None
    if has_750 and has_18k:
        findings.append(("Contraste", "750 / 18K"))
    elif has_750:
        findings.append(("Contraste", "750"))
    elif has_18k:
        findings.append(("Contraste", "18K"))
    elif has_925:
        findings.append(("Contraste", "Plata 925"))

    plaque = re.search(r"Plaqu[eé]\s+Or\s+G?(?:\s*20\s*µm)?", text, re.IGNORECASE)
    if plaque and not findings:
        findings.append(("Acabado Noble", "Plaqué Or G (20 micras)"))

    serial = re.search(r"(?:Matr[íi]cula|N[úu]mero\s+de\s+Serie\s+Registrado|Serie)\s*:\s*([A-Z0-9\- ]{4,20})", text, re.IGNORECASE)
    if serial:
        findings.append(("Nº de Serie", serial.group(1).strip()))

    origin = re.search(r"Procedencia\s*:\s*([^\.\n]{3,40})", text, re.IGNORECASE)
    if origin:
        findings.append(("Procedencia", origin.group(1).strip()))

    datacion = re.search(r"Dataci[oó]n\s+Estimada\s*:\s*([^\.\n]{4,45})", text, re.IGNORECASE)
    if datacion:
        findings.append(("Datación", datacion.group(1).strip()))

    confidence = re.search(r"NIVEL\s+DE\s+CONFIANZA(?:\s+PERICIAL)?\s*:\s*([\d\.,]+\s*%)", text, re.IGNORECASE)
    if confidence:
        findings.append(("Confianza Pericial", confidence.group(1).replace(" ", "")))
    return findings


def _choice_options(question: str):
    lowered = question.lower()
    if any(token in lowered for token in ("hueca", "maciza", "electroform", "canna vuota")):
        return ["", "Maciza", "Hueca"]
    return None


def unanswered_questions(alerts_text: str, metadata: dict) -> list:
    answers = metadata.get("question_answers") or {}
    questions = extract_questions_from_alerts(alerts_text)
    pending = []
    for question in questions:
        stored = answers.get(question, "")
        if _is_substantive_answer(stored):
            continue
        pending.append(question)
    return pending


def normalize_actionable_request(item) -> dict | None:
    """Vista segura para UI: dict plano con user_prompt y request_type (Supabase / Pydantic / legado)."""
    if item is None:
        return None
    if isinstance(item, dict):
        raw = item
    elif hasattr(item, "model_dump"):
        try:
            raw = item.model_dump()
        except Exception:
            return None
    else:
        return None

    user_prompt = str(raw.get("user_prompt") or "").strip()
    if not user_prompt:
        return None

    request_type = str(raw.get("request_type") or "verificacion_visual").strip()
    if request_type not in ("necesita_foto", "necesita_medida", "verificacion_visual"):
        request_type = "verificacion_visual"
    return {"user_prompt": user_prompt, "request_type": request_type}


def pending_actionable_requests(metadata: dict, alerts_text: str = "") -> list[dict]:
    """
    Peticiones pendientes del informe forense estructurado (solo user_prompt en UI).
    Si no hay recomendaciones JSON, usa extracto legado del dictamen sin internal_reasoning.
    """
    meta = metadata or {}
    forensic = meta.get("forensic_report") or {}
    answers = meta.get("question_answers") or {}
    resolved_prompts = {
        str(r.get("pregunta_original") or "").strip()
        for r in (forensic.get("preguntas_resueltas") or [])
        if isinstance(r, dict) and str(r.get("pregunta_original") or "").strip()
    }
    pending: list[dict] = []

    for item in forensic.get("recomendaciones") or []:
        view = normalize_actionable_request(item)
        if not view:
            try:
                from agents.schemas import ActionableRequest

                view = normalize_actionable_request(ActionableRequest.model_validate(item))
            except Exception:
                continue
        if not view:
            continue
        if view["user_prompt"] in resolved_prompts:
            continue
        if _is_substantive_answer(answers.get(view["user_prompt"], "")):
            continue
        pending.append(view)

    if pending:
        return pending

    for question in extract_questions_from_alerts(alerts_text or ""):
        if _is_substantive_answer(answers.get(question, "")):
            continue
        view = normalize_actionable_request(
            {
                "user_prompt": question,
                "request_type": "verificacion_visual",
            }
        )
        if view:
            pending.append(view)
    return pending
