"""Generador de Dossier Ejecutivo PDF — estética Quiet Luxury (reportlab)."""

from __future__ import annotations

import os
import re
import tempfile
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

import requests
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image as FlowImage,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String

from utils.parsers import _extract_true_market_valuation, executive_findings

# Paleta editorial
PAPER = HexColor("#F9F7F2")
FRAME = HexColor("#E5DFD3")
INK = HexColor("#1C1B19")
ACCENT = HexColor("#6E6558")
MUTED = HexColor("#8A8278")
WHITE = colors.white

BRAND = "CH CURIOSITIES HUNTER — PRIVATE ARCHIVE"
_MARGIN = 46
_HEADER_Y = 52
_FOOTER_Y = 38

_FONTS_READY = False


def _ensure_fonts() -> None:
    global _FONTS_READY
    if _FONTS_READY:
        return
    regular = "/System/Library/Fonts/Supplemental/Arial.ttf"
    bold = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    if os.path.exists(regular) and os.path.exists(bold):
        pdfmetrics.registerFont(TTFont("CHBody", regular))
        pdfmetrics.registerFont(TTFont("CHBody-Bold", bold))
    _FONTS_READY = True


def _font(bold: bool = False) -> str:
    _ensure_fonts()
    if "CHBody" in pdfmetrics.getRegisteredFontNames():
        return "CHBody-Bold" if bold else "CHBody"
    return "Helvetica-Bold" if bold else "Helvetica"


def _clean(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = "".join(ch if ord(ch) < 592 or ch in "€—–•·" else " " for ch in text)
    text = re.sub(r"\s+", " ", text).strip()
    if _font() == "Helvetica":
        text = text.replace("€", " EUR")
    return text


def _xml(value: Any) -> str:
    return _clean(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _br(value: str) -> str:
    return "<br/>".join(_xml(line) for line in str(value).splitlines() if str(line).strip())


def _styles() -> dict[str, ParagraphStyle]:
    body = _font()
    bold = _font(True)
    return {
        "kicker": ParagraphStyle(
            "kicker",
            fontName=bold,
            fontSize=7.5,
            leading=10,
            textColor=ACCENT,
            alignment=TA_LEFT,
            spaceAfter=4,
        ),
        "title": ParagraphStyle(
            "title",
            fontName=bold,
            fontSize=20,
            leading=24,
            textColor=INK,
            spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            fontName=body,
            fontSize=10,
            leading=13,
            textColor=MUTED,
            spaceAfter=8,
        ),
        "section": ParagraphStyle(
            "section",
            fontName=bold,
            fontSize=11,
            leading=14,
            textColor=INK,
            spaceBefore=14,
            spaceAfter=6,
        ),
        "h2": ParagraphStyle(
            "h2",
            fontName=bold,
            fontSize=10,
            leading=13,
            textColor=INK,
            spaceBefore=8,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            fontName=body,
            fontSize=9,
            leading=12.5,
            textColor=INK,
            spaceAfter=3,
        ),
        "muted": ParagraphStyle(
            "muted",
            fontName=body,
            fontSize=8.5,
            leading=11,
            textColor=MUTED,
            spaceAfter=3,
        ),
        "label": ParagraphStyle(
            "label",
            fontName=bold,
            fontSize=7.5,
            leading=10,
            textColor=ACCENT,
            spaceAfter=2,
        ),
        "cell": ParagraphStyle(
            "cell",
            fontName=body,
            fontSize=8.5,
            leading=11,
            textColor=INK,
        ),
        "value_band": ParagraphStyle(
            "value_band",
            fontName=bold,
            fontSize=14,
            leading=17,
            textColor=INK,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
    }


def _download_image_if_needed(src: str, cache_dir: str, index: int) -> str | None:
    if not src:
        return None
    if os.path.isfile(src):
        return src
    if not str(src).lower().startswith(("http://", "https://")):
        return None
    os.makedirs(cache_dir, exist_ok=True)
    ext = os.path.splitext(str(src).split("?")[0])[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        ext = ".jpg"
    dest = os.path.join(cache_dir, f"evidence_{index + 1}{ext}")
    if os.path.isfile(dest):
        return dest
    try:
        response = requests.get(src, timeout=15)
        if response.status_code != 200:
            return None
        with open(dest, "wb") as handle:
            handle.write(response.content)
        return dest
    except Exception:
        return None


def _flow_image(path: str, max_w: float, max_h: float) -> FlowImage | None:
    try:
        with PILImage.open(path) as source:
            image = source.convert("RGB")
            w, h = image.size
            scale = min(max_w / w, max_h / h, 1.0)
            nw, nh = w * scale, h * scale
            if scale < 1.0:
                image = image.resize((int(nw), int(nh)), PILImage.Resampling.LANCZOS)
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=82)
            buffer.seek(0)
        return FlowImage(buffer, width=nw, height=nh)
    except Exception:
        return None


def _section_rule_table(label: str, styles: dict) -> Table:
    rule = Table(
        [[Paragraph(_xml(label.upper()), styles["kicker"])]],
        colWidths=[A4[0] - 2 * _MARGIN],
    )
    rule.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, FRAME),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return rule


def _attr_table(rows: list[tuple[str, str]], styles: dict) -> Table | Paragraph:
    if not rows:
        return Paragraph("Sin atributos consignados.", styles["muted"])
    data = [
        [Paragraph(_xml(k), styles["label"]), Paragraph(_xml(v), styles["cell"])]
        for k, v in rows
        if _clean(v)
    ]
    if not data:
        return Paragraph("Sin atributos consignados.", styles["muted"])
    table = Table(data, colWidths=[130, A4[0] - 2 * _MARGIN - 130])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, FRAME),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _markdown_to_flows(text: str, styles: dict) -> list:
    flows: list = []
    raw = re.sub(r"<!--.*?-->", "", text or "", flags=re.S)
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            flows.append(Spacer(1, 4))
            continue
        if stripped in {"---", "***", "___"}:
            continue
        if stripped.startswith("|") and set(stripped.replace("|", "").replace("-", "").replace(":", "").strip()) <= {""}:
            continue

        style = styles["body"]
        content = stripped

        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            content = stripped.lstrip("#").strip()
            content = re.sub(r"\*+", "", content)
            style = styles["section"] if level <= 2 else styles["h2"]
        elif stripped.startswith("|"):
            cells = [re.sub(r"[*`_]", "", c).strip() for c in stripped.strip("|").split("|")]
            content = "  ·  ".join(c for c in cells if c)
        else:
            content = re.sub(r"\*\*([^*]+)\*\*", r"\1", content)
            content = re.sub(r"\*([^*]+)\*", r"\1", content)
            content = re.sub(r"`([^`]+)`", r"\1", content)
            content = re.sub(r"^[-*•]\s+", "• ", content)
            content = re.sub(r"^(\d+[\.\)])\s+", r"\1 ", content)

        content = re.sub(r"[*`_]", "", content)
        if content:
            flows.append(Paragraph(_xml(content), style))
    if not flows:
        flows.append(Paragraph("Sin contenido de dictamen disponible.", styles["muted"]))
    return flows


def _cad_schematic_flow(cad: dict, styles: dict) -> list:
    if not cad:
        return [Paragraph("Plano técnico CAD no disponible para este expediente.", styles["muted"])]

    w, h = 360, 140
    drawing = Drawing(w, h)
    drawing.add(Rect(0, 0, w, h, fillColor=PAPER, strokeColor=FRAME, strokeWidth=0.5))
    drawing.add(
        Rect(w * 0.25, h * 0.35, w * 0.5, h * 0.35, fillColor=None, strokeColor=ACCENT, strokeWidth=0.8)
    )
    drawing.add(Circle(w * 0.5, h * 0.52, 18, fillColor=None, strokeColor=INK, strokeWidth=0.7))
    drawing.add(Line(w * 0.3, h * 0.35, w * 0.7, h * 0.35, strokeColor=INK, strokeWidth=0.5))

    label = _clean(cad.get("jewelry_type") or "Pieza de joyería")
    drawing.add(String(8, h - 14, label[:48], fontName=_font(), fontSize=8, fillColor=ACCENT))

    dims = []
    for key, lbl in (
        ("cota_a_mm", "Ø int."),
        ("cota_b_mm", "Banda"),
        ("cota_c_mm", "Esp."),
        ("cota_d_mm", "Alt."),
        ("weight_g", "Peso g"),
    ):
        val = cad.get(key)
        if val not in (None, "", 0, "0"):
            dims.append(f"{lbl} {val} mm" if key != "weight_g" else f"Peso {val} g")
    if cad.get("total_ct"):
        dims.append(f"CT total {cad.get('total_ct')}")
    foot = " · ".join(dims) if dims else "Cotas pendientes de registro en taller."
    drawing.add(String(8, 6, foot[:90], fontName=_font(), fontSize=7, fillColor=MUTED))

    try:
        from reportlab.graphics import renderPM

        pil = renderPM.drawToPIL(drawing)
        buf = BytesIO()
        pil.save(buf, format="PNG")
        buf.seek(0)
        img = FlowImage(buf, width=w * 0.72, height=h * 0.72)
        return [img, Spacer(1, 6), Paragraph(_xml(foot), styles["muted"])]
    except Exception:
        rows = [(k.replace("_", " ").title(), str(v)) for k, v in cad.items() if v not in (None, "", [], {})]
        rows = rows[:12]
        return [_attr_table(rows, styles)]


def _comparables_table(items: list, styles: dict) -> Table | Paragraph:
    if not items:
        return Paragraph("Sin comparables estructurados en fase 2.", styles["muted"])
    head = [
        Paragraph("FUENTE", styles["label"]),
        Paragraph("REFERENCIA", styles["label"]),
        Paragraph("PRECIO / RELEVANCIA", styles["label"]),
    ]
    body = []
    for item in items[:6]:
        if not isinstance(item, dict):
            continue
        body.append(
            [
                Paragraph(_xml(item.get("source") or "—"), styles["cell"]),
                Paragraph(_xml(item.get("title") or "—"), styles["cell"]),
                Paragraph(
                    _xml(
                        " · ".join(
                            x
                            for x in (
                                item.get("price_estimate"),
                                item.get("similarity_or_relevance"),
                            )
                            if _clean(x)
                        )
                        or "—"
                    ),
                    styles["cell"],
                ),
            ]
        )
    if not body:
        return Paragraph("Sin comparables estructurados en fase 2.", styles["muted"])
    table = Table([head] + body, colWidths=[80, 170, A4[0] - 2 * _MARGIN - 250])
    table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, FRAME),
                ("LINEBELOW", (0, 1), (-1, -1), 0.25, FRAME),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _page_canvas(case_id: str, issued: str):
    def _draw(canvas, doc):
        canvas.saveState()
        w, h = A4
        canvas.setFillColor(PAPER)
        canvas.rect(0, 0, w, h, fill=1, stroke=0)
        canvas.setStrokeColor(FRAME)
        canvas.setLineWidth(0.5)
        canvas.line(_MARGIN, h - _HEADER_Y, w - _MARGIN, h - _HEADER_Y)
        canvas.setFillColor(ACCENT)
        canvas.setFont(_font(), 7.5)
        canvas.drawString(_MARGIN, h - _HEADER_Y + 10, _clean(case_id)[:40])
        canvas.setFont(_font(True), 7)
        canvas.drawCentredString(w / 2, h - _HEADER_Y + 10, BRAND)
        canvas.setFont(_font(), 7.5)
        canvas.drawRightString(w - _MARGIN, h - _HEADER_Y + 10, issued)
        canvas.line(_MARGIN, _FOOTER_Y, w - _MARGIN, _FOOTER_Y)
        canvas.setFillColor(MUTED)
        canvas.setFont(_font(), 7)
        canvas.drawRightString(w - _MARGIN, _FOOTER_Y - 12, f"Pág. {canvas.getPageNumber()}")
        canvas.restoreState()

    return _draw


def generate_dossier_pdf(
    case_data: dict,
    image_paths: list[str] | None = None,
    cad_svg_or_png_path: str | None = None,
) -> bytes:
    """Maqueta un dossier multipágina editorial y devuelve los bytes del PDF."""
    case_data = dict(case_data or {})
    styles = _styles()
    case_id = _clean(case_data.get("case_id") or "EXP-SIN-REF")
    title = _clean(case_data.get("title") or case_data.get("object_description") or "Pieza en archivo")
    maker = _clean(case_data.get("maker") or case_data.get("brand") or "")
    taxonomy = _clean(
        case_data.get("domain_taxonomy")
        or case_data.get("category")
        or (case_data.get("forensic_report") or {}).get("category_name")
        or "Sin taxonomía"
    )
    dictamen = case_data.get("dictamen_text") or case_data.get("dictamen") or ""

    ts = case_data.get("timestamp")
    if isinstance(ts, (int, float)) and ts > 0:
        issued = datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%d.%m.%Y")
    else:
        issued = datetime.now(timezone.utc).strftime("%d.%m.%Y")

    val_info = case_data.get("valuation") or _extract_true_market_valuation(dictamen, case_data)
    findings = dict(executive_findings(dictamen))
    summary_bits = [findings[k] for k in sorted(findings.keys()) if findings.get(k)]
    executive = " · ".join(summary_bits[:5]) if summary_bits else _clean(
        (case_data.get("forensic_report") or {}).get("technical_summary")
        or "Resumen pericial disponible en el cuerpo del dictamen."
    )

    cache_dir = os.path.join(tempfile.gettempdir(), "ch_dossier", case_id.replace("/", "_"))
    resolved_images: list[str] = []
    for idx, src in enumerate(image_paths or []):
        local = _download_image_if_needed(src, cache_dir, idx)
        if local:
            resolved_images.append(local)

    forensic = case_data.get("forensic_report") or {}
    market = case_data.get("market_valuation_report") or {}
    logistics = case_data.get("logistics_arbitrage_report") or {}
    logistics_local = case_data.get("logistics_intelligence") or {}
    cad = case_data.get("cad_blueprint") or {}

    story: list = []

    # Bloque 1 — Identidad y evidencia
    story.append(_section_rule_table("I · Identidad y evidencia visual", styles))
    story.append(Spacer(1, 8))
    story.append(Paragraph(_xml(title.upper()), styles["title"]))
    subtitle_parts = [p for p in (maker, taxonomy) if p]
    if subtitle_parts:
        story.append(Paragraph(_xml(" · ".join(subtitle_parts)), styles["subtitle"]))
    story.append(Paragraph(f"<b>Expediente</b> {_xml(case_id)}", styles["body"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph("RESUMEN EJECUTIVO", styles["label"]))
    story.append(Paragraph(_xml(executive), styles["body"]))
    story.append(Spacer(1, 10))

    if resolved_images:
        hero = _flow_image(resolved_images[0], 200 * mm / mm, 130 * mm / mm)
        if hero:
            frame = Table([[hero]], colWidths=[A4[0] - 2 * _MARGIN])
            frame.setStyle(
                TableStyle(
                    [
                        ("BOX", (0, 0), (-1, -1), 0.5, FRAME),
                        ("BACKGROUND", (0, 0), (-1, -1), WHITE),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            story.append(frame)
        if len(resolved_images) > 1:
            thumbs = []
            for path in resolved_images[1:5]:
                thumb = _flow_image(path, 115, 82)
                if thumb:
                    thumbs.append(thumb)
            if thumbs:
                rows = [thumbs[i : i + 3] for i in range(0, len(thumbs), 3)]
                for row in rows:
                    while len(row) < 3:
                        row.append("")
                    tbl = Table([row], colWidths=[155, 155, 155])
                    tbl.setStyle(
                        TableStyle(
                            [
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                            ]
                        )
                    )
                    story.append(Spacer(1, 8))
                    story.append(tbl)
    else:
        story.append(Paragraph("Sin evidencia fotográfica enlazada.", styles["muted"]))

    story.append(PageBreak())

    # Bloque 2 — Forense y CAD
    story.append(_section_rule_table("II · Dictamen forense y plano técnico CAD", styles))
    story.append(Spacer(1, 8))

    dim = forensic.get("dimensions_mm") or {}
    dim_rows = []
    if isinstance(dim, dict):
        for k in ("length", "width", "height", "diameter"):
            if dim.get(k):
                dim_rows.append((k.title(), f"{dim[k]} mm"))
    attr_rows = [
        ("Taxonomía", taxonomy),
        ("Materiales", ", ".join(forensic.get("primary_materials") or []) or "—"),
        ("Ley / grado", forensic.get("purity_or_grade") or "—"),
        ("Peso / volumen", forensic.get("estimated_weight_or_volume") or "—"),
        ("Confianza forense", f"{forensic.get('confidence_score') or '—'} / 100"),
    ]
    try:
        from agents.schemas import SERIAL_DECODING_FIELD_KEYS
        from utils.discipline import serial_decoding_ficha_rows

        for label, val in serial_decoding_ficha_rows(case_data):
            attr_rows.append((label, val))
        skip_serial = set(SERIAL_DECODING_FIELD_KEYS)
    except ImportError:
        skip_serial = set()
    for key, val in (forensic.get("key_attributes") or {}).items():
        if key in skip_serial:
            continue
        attr_rows.append((str(key).replace("_", " ").title(), str(val)))

    story.append(Paragraph("ATRIBUTOS CLAVE", styles["label"]))
    story.append(_attr_table(attr_rows + dim_rows, styles))
    story.append(Spacer(1, 8))

    auth = forensic.get("authenticity_signals") or []
    anomalies = forensic.get("anomalies_detected") or []
    if auth or anomalies:
        story.append(Paragraph("HALLAZGOS DE AUTENTICIDAD", styles["label"]))
        for sig in auth[:8]:
            story.append(Paragraph(f"• {_xml(sig)}", styles["body"]))
        for an in anomalies[:5]:
            story.append(Paragraph(f"• Anomalía: {_xml(an)}", styles["muted"]))
    else:
        story.append(Paragraph("Hallazgos de autenticidad: ver dictamen completo (fase legada).", styles["muted"]))

    story.append(Spacer(1, 10))
    story.append(Paragraph("PLANO TÉCNICO", styles["label"]))
    cad_flows: list = []
    if cad_svg_or_png_path and os.path.isfile(cad_svg_or_png_path):
        ext = os.path.splitext(cad_svg_or_png_path)[1].lower()
        if ext in (".png", ".jpg", ".jpeg", ".webp"):
            img = _flow_image(cad_svg_or_png_path, 280, 160)
            if img:
                cad_flows = [img]
        elif ext == ".svg":
            try:
                from svglib.svglib import svg2rlg
                from reportlab.graphics import renderPM

                drawing = svg2rlg(cad_svg_or_png_path)
                if drawing:
                    pil = renderPM.drawToPIL(drawing)
                    buf = BytesIO()
                    pil.save(buf, format="PNG")
                    buf.seek(0)
                    cad_flows = [FlowImage(buf, width=280, height=160)]
            except Exception:
                cad_flows = _cad_schematic_flow(cad, styles)
        else:
            cad_flows = _cad_schematic_flow(cad, styles)
    else:
        cad_flows = _cad_schematic_flow(cad, styles)
    story.extend(cad_flows)

    tech = _clean(forensic.get("technical_summary"))
    if tech:
        story.append(Spacer(1, 8))
        story.append(Paragraph("SÍNTESIS TÉCNICA", styles["label"]))
        story.append(Paragraph(_xml(tech), styles["body"]))

    story.append(PageBreak())

    # Bloque 3 — Mercado y arbitraje
    story.append(_section_rule_table("III · Inteligencia de mercado y arbitraje", styles))
    story.append(Spacer(1, 8))

    band = _clean(val_info.get("display") or "—")
    band_table = Table(
        [[Paragraph(band, styles["value_band"])]],
        colWidths=[A4[0] - 2 * _MARGIN],
    )
    band_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, FRAME),
                ("BACKGROUND", (0, 0), (-1, -1), WHITE),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(band_table)
    story.append(Spacer(1, 6))
    tiers = Table(
        [
            [
                Paragraph(f"Liquidez\n{_xml(val_info.get('wholesale', '—'))}", styles["cell"]),
                Paragraph(f"Subasta\n{_xml(val_info.get('auction', '—'))}", styles["cell"]),
                Paragraph(f"Minorista\n{_xml(val_info.get('retail', '—'))}", styles["cell"]),
            ]
        ],
        colWidths=[(A4[0] - 2 * _MARGIN) / 3] * 3,
    )
    tiers.setStyle(
        TableStyle(
            [
                ("LINEAFTER", (0, 0), (-2, -1), 0.25, FRAME),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(tiers)
    story.append(Spacer(1, 10))

    demand = _clean(market.get("demand_trend") or "Sin tendencia estructurada.")
    story.append(Paragraph("TENDENCIA DE DEMANDA", styles["label"]))
    story.append(Paragraph(_xml(demand), styles["body"]))
    rationale = _clean(market.get("pricing_rationale"))
    if rationale:
        story.append(Paragraph(_xml(rationale), styles["muted"]))

    story.append(Spacer(1, 8))
    story.append(Paragraph("COMPARABLES RELEVANTES", styles["label"]))
    comparables = (market.get("external_comparables") or []) + (market.get("internal_precedents_used") or [])
    story.append(_comparables_table(comparables, styles))

    hs = logistics.get("hs_code_estimate") or "—"
    hs_desc = logistics.get("hs_code_description") or ""
    cites = logistics.get("cites_or_restricted_materials")
    cites_txt = "Revisión CITES / materiales restringidos recomendada." if cites else "Sin alerta CITES estructurada en fase 2."
    hub = (
        logistics.get("recommended_primary_hub")
        or (logistics_local.get("origin_location") or {}).get("city")
        or "—"
    )
    alerts = logistics.get("regulatory_alerts") or []
    alert_line = " · ".join(_clean(a) for a in alerts[:4]) if alerts else cites_txt

    story.append(Spacer(1, 10))
    story.append(
        _attr_table(
            [
                ("HS Code", f"{hs} — {hs_desc}".strip(" —")),
                ("Alertas regulatorias", alert_line),
                ("Plaza recomendada", _clean(hub)),
                ("Techo adquisición", _clean(market.get("recommended_acquisition_ceiling") or "—")),
            ],
            styles,
        )
    )

    story.append(PageBreak())

    # Bloque 4 — Dictamen completo
    story.append(_section_rule_table("IV · Dictamen editorial completo", styles))
    story.append(Spacer(1, 8))
    story.extend(_markdown_to_flows(dictamen, styles))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=_MARGIN,
        rightMargin=_MARGIN,
        topMargin=_HEADER_Y + 18,
        bottomMargin=_FOOTER_Y + 14,
        title=f"Dossier {case_id}",
        author=BRAND,
    )
    doc.case_id = case_id
    page_fn = _page_canvas(case_id, f"Emisión {issued}")
    doc.build(story, onFirstPage=page_fn, onLaterPages=page_fn)
    return buffer.getvalue()