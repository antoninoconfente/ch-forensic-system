"""Bloques editoriales de detalle: metrología, logística y gemología."""

from __future__ import annotations

import html
from collections.abc import Callable

from nicegui import ui

from src.research.gemology import (
    AUTHORSHIPS,
    GEM_CLARITIES,
    GEM_COLORS,
    GEM_CUTS,
    GEM_NATURES,
    GEM_SPECIES,
    METALS,
    PEARL_LUSTER,
    PEARL_MATCHING,
    PEARL_NACRE,
    PEARL_NATURES,
    PEARL_SURFACE,
    SETTINGS,
    SUBJECTS,
    format_eur as format_gem_eur,
    value_piece,
)
from src.research.logistics import format_eur
from ui.theme import editorial_button
from utils.discipline import (
    forensic_dimensions_dict,
    measurement_guide_for_case,
    resolve_discipline_label,
    resolve_mass_grams,
    spec_value_is_present,
)


def render_logistics_arbitrage_report(report: dict, val_display: str) -> None:
    if not report:
        ui.html(
            "<p class='micro-coord text-[#625E57] m-0 py-4'>"
            "Informe de arbitraje pendiente. Ejecute una investigación con el agente logístico "
            "para poblar HS Code, CITES y la comparativa de hubs."
            "</p>"
        )
        return

    hs = report.get("hs_code_estimate") or "—"
    hs_desc = report.get("hs_code_description") or ""
    cites = report.get("cites_or_restricted_materials")
    cites_txt = (
        "CITES / materiales restringidos — despacho especializado"
        if cites
        else "Sin alerta CITES estructurada"
    )
    alerts = report.get("regulatory_alerts") or []
    alert_body = " · ".join(str(a) for a in alerts[:6]) if alerts else cites_txt
    hub_a = report.get("recommended_primary_hub") or "—"
    hub_b = report.get("recommended_backup_hub") or "—"
    max_buy = report.get("recommended_max_buy_price")
    max_buy_txt = format_eur(float(max_buy)) if max_buy not in (None, "", 0) else "—"
    margin_note = (report.get("net_margin_rationale") or "").strip()

    rows = [
        ("Partida arancelaria (HS)", f"{hs} — {hs_desc}".strip(" —")),
        ("Descripción aduanera", hs_desc or "—"),
        ("Alertas regulatorias / CITES", alert_body),
        ("Plaza principal", hub_a),
        ("Plaza secundaria", hub_b),
        ("Techo máx. de compra", max_buy_txt),
        ("Base de tasación", val_display or "—"),
    ]
    rows_html = "".join(
        f"<div class='spec-row'><span class='spec-label'>{html.escape(lbl)}</span>"
        f"<span class='spec-value'>{html.escape(val)}</span></div>"
        for lbl, val in rows
    )
    ui.html(f"<div class='spec-table w-full'>{rows_html}</div>")

    if margin_note:
        ui.html(f"<p class='text-[11px] text-[#625E57] leading-snug mt-2 m-0'>{html.escape(margin_note)}</p>")

    routes = report.get("route_comparison") or []
    if routes:
        ui.html("<span class='micro-coord mt-4 block'>COMPARATIVA DE HUBS INTERNACIONALES</span>")
        body = ""
        for row in routes[:8]:
            if not isinstance(row, dict):
                continue
            hub = row.get("hub_city") or "—"
            sale = row.get("estimated_sale_price")
            fee_pct = row.get("auction_or_broker_fee_pct")
            ship = row.get("shipping_insurance_cost")
            net = row.get("net_proceeds_estimate")
            buyer = (row.get("buyer_profile") or "").strip()
            line = " · ".join(
                x
                for x in (
                    format_eur(float(sale)) if sale not in (None, 0) else "—",
                    f"Comisión {fee_pct:g}%" if fee_pct else "",
                    f"Tránsito {format_eur(float(ship))}" if ship not in (None, 0) else "",
                    f"Neto {format_eur(float(net))}" if net not in (None, 0) else "",
                )
                if x
            )
            if buyer:
                hub = f"{hub} ({buyer})"
            body += (
                f"<div class='spec-row'><span class='spec-label'>{html.escape(str(hub))}</span>"
                f"<span class='spec-value'>{html.escape(line or '—')}</span></div>"
            )
        ui.html(f"<div class='spec-table w-full mt-2'>{body}</div>")


def render_physical_metrology_block(case_data: dict) -> None:
    """Metrología genérica — sin SVG de joyería."""
    dims = forensic_dimensions_dict(case_data)
    cad = case_data.get("cad_blueprint") if isinstance(case_data.get("cad_blueprint"), dict) else {}
    guide = measurement_guide_for_case(case_data)
    discipline = resolve_discipline_label(case_data)
    peso = resolve_mass_grams(case_data)

    def _dim(key_forensic: str, *cad_keys: str) -> str:
        if dims.get(key_forensic) not in (None, ""):
            return str(dims[key_forensic])
        for ck in cad_keys:
            if cad.get(ck) not in (None, "", 0):
                return str(cad[ck])
        return ""

    cota_x = _dim("length", "cota_x_mm", "length_mm", "cota_b_mm")
    cota_y = _dim("width", "cota_y_mm", "width_mm", "cota_a_mm")
    cota_z = _dim("height", "cota_z_mm", "height_mm", "cota_d_mm", "cota_c_mm")

    ui.html(
        "<span class='micro-coord text-[#141413]'>"
        "/// METROLOGÍA Y COTAS FÍSICAS"
        "</span>"
    )
    ui.html(f"<p class='text-[11px] text-[#625E57] m-0 mb-2'>{html.escape(discipline)}</p>")

    with ui.row().classes("w-full justify-center py-2"):
        ui.icon("straighten", size="2rem", color="#6E6558")

    rows = [
        ("Cota X (mm)", cota_x),
        ("Cota Y (mm)", cota_y),
        ("Cota Z (mm)", cota_z),
        ("Peso total (g)", peso),
    ]
    visible = [(l, v) for l, v in rows if spec_value_is_present(v)]
    if visible:
        rows_html = "".join(
            f"<div class='spec-row'><span class='spec-label'>{html.escape(l)}</span>"
            f"<span class='spec-value'>{html.escape(str(v))}</span></div>"
            for l, v in visible
        )
        ui.html(f"<div class='spec-table w-full'>{rows_html}</div>")
    else:
        ui.html(
            "<p class='micro-coord text-[#625E57] m-0'>"
            "Cotas y peso pendientes de verificación en mano."
            "</p>"
        )
    ui.html(
        f"<p class='text-[11px] text-[#625E57] leading-relaxed m-0 mt-3 px-1 border-t border-[#B8B2A4] pt-3'>"
        f"<span class='micro-coord'>GUÍA DE MEDICIÓN</span><br/>{html.escape(guide)}"
        f"</p>"
    )


def render_gemology_calculator(
    *,
    case_id: str,
    dictamen_text: str,
    seeded_gem: dict,
    can_save: bool,
    spot_prices: Callable[[], dict],
    on_persist: Callable[[str, dict, str], None],
    on_after_save: Callable[[], None],
) -> None:
    ui.html(
        "<span class='micro-coord text-[#141413] mt-4 block'>"
        "/// GEMOLOGÍA Y METALES PRECIOSOS"
        "</span>"
    )
    gem_state = {
        "applies": bool(seeded_gem.get("applies")),
        "subject": seeded_gem.get("subject"),
        "metal_kind": seeded_gem["metal"]["kind"],
        "metal_grams": float(seeded_gem["metal"].get("grams") or 0.0),
        "authorship": seeded_gem.get("authorship"),
        "setting": seeded_gem.get("setting"),
        "gem": dict(seeded_gem.get("gem") or {}),
        "pearl": dict(seeded_gem.get("pearl") or {}),
    }
    gem_container = ui.column().classes("w-full gap-3 human-evidence-box")

    def render_controls():
        gem_container.clear()
        with gem_container:
            applies_cb = ui.checkbox(
                "La pieza incorpora gemas o perlas",
                value=gem_state["applies"],
            ).props("color=dark")
            applies_cb.on_value_change(lambda e: (gem_state.update({"applies": e.value}), render_controls()))

            if gem_state["applies"]:
                subj_radio = ui.radio(SUBJECTS, value=gem_state["subject"]).props("inline dense color=dark")
                subj_radio.on_value_change(lambda e: (gem_state.update({"subject": e.value}), render_controls()))

                with ui.row().classes("w-full grid grid-cols-1 sm:grid-cols-2 gap-4"):
                    ui.select(METALS, value=gem_state["metal_kind"], label="Metal base").on_value_change(
                        lambda e: (gem_state.update({"metal_kind": e.value}), render_controls())
                    ).classes("w-full")
                    ui.number(label="Gramos de metal", value=gem_state["metal_grams"], min=0.0, step=0.1).on_value_change(
                        lambda e: (gem_state.update({"metal_grams": float(e.value or 0.0)}), render_controls())
                    ).classes("w-full")
                    ui.select(AUTHORSHIPS, value=gem_state["authorship"], label="Autoría o taller").on_value_change(
                        lambda e: (gem_state.update({"authorship": e.value}), render_controls())
                    ).classes("w-full")
                    ui.select(SETTINGS, value=gem_state["setting"], label="Engaste").on_value_change(
                        lambda e: (gem_state.update({"setting": e.value}), render_controls())
                    ).classes("w-full")

                if gem_state["subject"] in ("Gema", "Gema y perla"):
                    ui.html("<span class='micro-coord mt-2'>PARÁMETROS DE GEMA</span>")
                    with ui.row().classes("w-full grid grid-cols-1 sm:grid-cols-3 gap-3"):
                        ui.select(GEM_SPECIES, value=gem_state["gem"]["species"], label="Especie").on_value_change(
                            lambda e: (gem_state["gem"].update({"species": e.value}), render_controls())
                        ).classes("w-full")
                        ui.number(
                            label="Quilates totales (ct)",
                            value=float(gem_state["gem"].get("carat") or 0),
                            min=0.0,
                            step=0.05,
                        ).on_value_change(
                            lambda e: (gem_state["gem"].update({"carat": float(e.value or 0)}), render_controls())
                        ).classes("w-full")
                        ui.select(GEM_COLORS, value=gem_state["gem"]["color"], label="Color").on_value_change(
                            lambda e: (gem_state["gem"].update({"color": e.value}), render_controls())
                        ).classes("w-full")
                        ui.select(GEM_CLARITIES, value=gem_state["gem"]["clarity"], label="Pureza").on_value_change(
                            lambda e: (gem_state["gem"].update({"clarity": e.value}), render_controls())
                        ).classes("w-full")
                        ui.select(GEM_CUTS, value=gem_state["gem"]["cut"], label="Talla").on_value_change(
                            lambda e: (gem_state["gem"].update({"cut": e.value}), render_controls())
                        ).classes("w-full")
                        ui.select(GEM_NATURES, value=gem_state["gem"]["nature"], label="Naturaleza").on_value_change(
                            lambda e: (gem_state["gem"].update({"nature": e.value}), render_controls())
                        ).classes("w-full")

                if gem_state["subject"] in ("Perla", "Gema y perla"):
                    ui.html("<span class='micro-coord mt-2'>PARÁMETROS DE PERLA</span>")
                    with ui.row().classes("w-full grid grid-cols-1 sm:grid-cols-3 gap-3"):
                        ui.select(PEARL_NATURES, value=gem_state["pearl"]["nature"], label="Naturaleza").on_value_change(
                            lambda e: (gem_state["pearl"].update({"nature": e.value}), render_controls())
                        ).classes("w-full")
                        ui.number(
                            label="Número de perlas",
                            value=int(gem_state["pearl"].get("count") or 0),
                            min=0,
                            step=1,
                        ).on_value_change(
                            lambda e: (gem_state["pearl"].update({"count": int(e.value or 0)}), render_controls())
                        ).classes("w-full")
                        ui.select(PEARL_LUSTER, value=gem_state["pearl"]["luster"], label="Lustre").on_value_change(
                            lambda e: (gem_state["pearl"].update({"luster": e.value}), render_controls())
                        ).classes("w-full")
                        ui.select(PEARL_NACRE, value=gem_state["pearl"]["nacre"], label="Nácar").on_value_change(
                            lambda e: (gem_state["pearl"].update({"nacre": e.value}), render_controls())
                        ).classes("w-full")
                        ui.select(PEARL_SURFACE, value=gem_state["pearl"]["surface"], label="Superficie").on_value_change(
                            lambda e: (gem_state["pearl"].update({"surface": e.value}), render_controls())
                        ).classes("w-full")
                        ui.select(PEARL_MATCHING, value=gem_state["pearl"]["matching"], label="Matching").on_value_change(
                            lambda e: (gem_state["pearl"].update({"matching": e.value}), render_controls())
                        ).classes("w-full")

            payload = {
                "applies": gem_state["applies"],
                "subject": gem_state["subject"],
                "gem": gem_state["gem"],
                "pearl": gem_state["pearl"],
                "setting": gem_state["setting"],
                "authorship": gem_state["authorship"],
                "metal": {"kind": gem_state["metal_kind"], "grams": gem_state["metal_grams"]},
            }
            valuation = value_piece(payload, spot_prices())
            payload["valuation"] = valuation

            if gem_state["applies"]:
                metal_val = (
                    "Introduzca gramos para calcular metal"
                    if valuation.get("metal_pending")
                    else format_gem_eur(valuation.get("metal_eur"))
                )
                ui.html(
                    "<div class='spec-table my-2'>"
                    f"<div class='spec-row'><span class='spec-label'>Metal base</span><span class='spec-value'>{metal_val}</span></div>"
                    f"<div class='spec-row'><span class='spec-label'>Gema / perla</span><span class='spec-value'>"
                    f"{format_gem_eur(valuation.get('gem_eur'))} · {format_gem_eur(valuation.get('pearl_eur'))}</span></div>"
                    f"<div class='spec-row'><span class='spec-label'>Tasación gemológica</span><span class='spec-value'>"
                    f"{format_gem_eur(valuation.get('piece_eur'))}</span></div>"
                    "</div>"
                )

            if can_save and gem_state["applies"]:

                def save_gem():
                    on_persist(case_id, payload, dictamen_text)
                    ui.notify("Gemología fijada en la ficha", type="positive")
                    on_after_save()

                editorial_button("FIJAR TASACIÓN GEMOLÓGICA EN LA FICHA", on_click=save_gem)

    render_controls()