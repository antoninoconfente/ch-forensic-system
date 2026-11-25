"""Bloques editoriales de detalle: metrología, logística y gemología."""

from __future__ import annotations

import html
import os
from collections.abc import Callable

from nicegui import ui

from auth.supabase_auth import is_admin_user
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
from ui.blueprints import (
    GEM_CUT_CATALOG,
    JEWELRY_TYPES,
    RING_SHANK_PROFILES,
    SETTING_ARCHITECTURES,
    SPECIES_DENSITY_MULTIPLIER,
    _dynamic_blueprint_svg_html,
    _plain_language_measurement_guide,
    estimate_carats_from_mm,
)
from ui.theme import editorial_button
from utils.discipline import (
    forensic_dimensions_dict,
    resolve_mass_grams,
    spec_value_is_present,
)


def _ui_options(options):
    """NiceGUI: opciones de radio/select deben ser listas (no tuplas) en refrescos reactivos."""
    if isinstance(options, dict):
        return options
    return list(options)


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


def render_public_ficha_spec_table(rows: list[tuple[str, str]]) -> None:
    """Tabla editorial de ficha técnica (Mesa de Auditoría — bloque público)."""
    visible = [(lbl, val) for lbl, val in rows if spec_value_is_present(val)]
    if not visible:
        ui.html(
            "<p class='micro-coord text-[#625E57] m-0'>Sin atributos técnicos consolidados en esta fase.</p>"
        )
        return
    rows_html = "".join(
        f"<div class='spec-row'><span class='spec-label'>{html.escape(lbl)}</span>"
        f"<span class='spec-value'>{html.escape(str(val))}</span></div>"
        for lbl, val in visible
    )
    ui.html(f"<div class='spec-table w-full'>{rows_html}</div>")


async def _extract_upload_bytes(e) -> tuple[str, bytes]:
    """Lee bytes de un evento ui.upload (misma convención que app.py)."""
    raw_name = getattr(e, "name", None)
    if not raw_name and hasattr(e, "file"):
        raw_name = getattr(e.file, "name", "evidence.jpg")
    raw_name = raw_name or "evidence.jpg"

    ext = os.path.splitext(raw_name)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        ext = ".jpg"
    safe_name = f"ev_{os.urandom(3).hex()}{ext}"

    if hasattr(e, "content") and e.content is not None:
        data = e.content.read()
        if hasattr(data, "__await__"):
            data = await data
    elif hasattr(e, "file") and e.file is not None:
        read_res = e.file.read()
        data = await read_res if hasattr(read_res, "__await__") else read_res
    else:
        data = b""

    return safe_name, data or b""


def render_resolved_requests_history(
    case_data: dict,
    *,
    question_answers: dict | None = None,
    widgets_out: dict[str, object] | None = None,
    files_out: dict[str, tuple[str, bytes]] | None = None,
) -> bool:
    """Historial editable de preguntas ya respondidas. Devuelve True si hay entradas."""
    forensic = case_data.get("forensic_report") if isinstance(case_data.get("forensic_report"), dict) else {}
    raw = forensic.get("preguntas_resueltas") or []
    items = [r for r in raw if isinstance(r, dict) and str(r.get("pregunta_original") or "").strip()]
    if not items:
        return False

    answers_map = question_answers if isinstance(question_answers, dict) else {}
    widgets_out = widgets_out if widgets_out is not None else {}
    files_out = files_out if files_out is not None else {}
    widgets_out.clear()
    files_out.clear()

    ui.html("<span class='micro-coord mt-2'>/// HISTORIAL DE RESOLUCIÓN</span>")
    with ui.column().classes("w-full gap-3 mt-2"):
        for entry in items:
            pregunta = str(entry.get("pregunta_original") or "").strip()
            stored = str(entry.get("respuesta_usuario") or "").strip()
            prior = str(answers_map.get(pregunta, stored) or "").strip()
            if prior in ("—",):
                prior = stored if stored != "—" else ""
            with ui.column().classes(
                "w-full gap-2 p-3 border border-[#E5E0D6] bg-[#F8F6F2] opacity-90"
            ):
                ui.html(
                    f"<p class='m-0 text-[11px] text-[#625E57] leading-relaxed'>{html.escape(pregunta)}</p>"
                )
                widgets_out[pregunta] = ui.input(
                    label="Respuesta (Editable)",
                    value=prior,
                    placeholder="Corrija o complete la respuesta registrada…",
                ).classes("w-full")

                def make_hist_up(q_key: str):
                    async def _up(e):
                        fname, fbytes = await _extract_upload_bytes(e)
                        if fbytes:
                            files_out[q_key] = (fname, fbytes)
                            ui.notify("Evidencia actualizada en el historial", type="positive")

                    return _up

                ui.upload(
                    label="Cambiar / adjuntar foto de evidencia",
                    auto_upload=True,
                    on_upload=make_hist_up(pregunta),
                ).props("accept=.jpg,.jpeg,.png,.webp flat").classes("w-full editorial-uploader")

    return True


# TEMP (QA UI): forzar caja negra visible sin depender del rol hasta validar el modal.
_XRAY_FORCE_VISIBLE = True


def xray_audit_visible() -> bool:
    """True si el panel Rayos X debe mostrarse (admin o modo forzado QA)."""
    if _XRAY_FORCE_VISIBLE:
        return True
    return is_admin_user()


def _trail_from_report_blob(blob: dict | None, phase: str) -> list[str]:
    if not isinstance(blob, dict):
        return []
    raw = blob.get("global_audit_trail") or []
    return [f"[{phase}] {str(x).strip()}" for x in raw if str(x).strip()]


def audit_trail_from_case(case_data: dict | None) -> list[str]:
    """Concatena global_audit_trail de Forense + Tasación + Logística."""
    if not isinstance(case_data, dict):
        return []
    merged: list[str] = []
    merged.extend(_trail_from_report_blob(case_data.get("forensic_report"), "FORENSE"))
    merged.extend(_trail_from_report_blob(case_data.get("market_valuation_report"), "TASACIÓN"))
    merged.extend(_trail_from_report_blob(case_data.get("logistics_arbitrage_report"), "LOGÍSTICA"))
    return merged


def normalized_audit_trail_chronological(
    audit_trail: list[str] | None, *, newest_first: bool = True
) -> list[str]:
    """Orden legible: por defecto la entrada más reciente arriba (append histórico en backend)."""
    entries = [str(x).strip() for x in (audit_trail or []) if str(x).strip()]
    if newest_first:
        return list(reversed(entries))
    return entries


def render_admin_blackbox(audit_trail: list[str] | None = None) -> None:
    """Consola de caja negra. Silencioso si xray_audit_visible() es False."""
    # Modo dios QA: _XRAY_FORCE_VISIBLE anula el corte por rol.
    if not xray_audit_visible():
        return

    entries = normalized_audit_trail_chronological(audit_trail, newest_first=True)
    ui.html(
        "<div class='w-full border-b border-[#1f3d24] pb-2 mb-3'>"
        "<p class='m-0 text-[10px] font-mono tracking-[0.22em] text-[#4ade80] uppercase'>"
        "Modo Rayos X · Admin</p>"
        "<p class='m-0 mt-1 text-[12px] font-mono text-[#bbf7d0]'>"
        "🕵️ REGISTRO DE IMPACTO (CAJA NEGRA)</p>"
        "<p class='m-0 mt-1 text-[10px] font-mono text-[#6b8f71]'>"
        "Orden: más reciente arriba</p></div>"
    )
    if not entries:
        ui.html(
            "<p class='m-0 text-[11px] font-mono text-[#6b8f71]'>"
            "Sin entradas de auditoría en este expediente.</p>"
        )
        return
    for index, line in enumerate(entries, start=1):
        ui.html(
            f"<div class='w-full mb-3 pb-2 border-b border-[#162816]'>"
            f"<p class='m-0 text-[9px] font-mono text-[#4ade80]'>#{index:02d}</p>"
            f"<p class='m-0 mt-1 text-[11px] leading-relaxed font-mono text-[#e2fbe8]'>"
            f"{html.escape(line)}</p></div>"
        )


def mount_admin_xray_dialog(audit_trail: list[str] | None = None):
    """Modal flotante con caja negra (compatible con vistas anidadas en column)."""
    if not xray_audit_visible():
        return None

    entries = normalized_audit_trail_chronological(audit_trail, newest_first=True)
    with ui.dialog() as dialog, ui.card().classes(
        "bg-grey-9 text-green-400 font-mono w-full max-w-2xl"
    ).style("max-height: 88vh"):
        ui.label("🕵️ MODO AUDITOR: CAJA NEGRA").classes("text-xl font-bold mb-2")
        ui.label("Orden: más reciente arriba").classes("text-caption text-grey-5 mb-4")
        with ui.scroll_area().classes("w-full").style("max-height: 60vh"):
            with ui.column().classes("w-full gap-2 pr-2"):
                if not entries:
                    ui.label("Sin entradas de auditoría en este expediente.").classes(
                        "text-grey-5"
                    )
                else:
                    for index, entry in enumerate(entries, start=1):
                        ui.label(f"#{index:02d}  {entry}").classes("mb-2 text-body2")
        ui.button("Cerrar", on_click=dialog.close).classes("mt-4")
    return dialog


def render_black_box_audit_trail(case_data: dict) -> None:
    """Compatibilidad: render inline (preferir mount_admin_xray_dialog en vista expediente)."""
    render_admin_blackbox(audit_trail_from_case(case_data))


def render_gemology_empty_state() -> None:
  """Estado vacío Quiet Luxury cuando el laboratorio gemológico no aplica."""
  with ui.column().classes("w-full items-center justify-center py-20 gap-5"):
    ui.icon("diamond", size="3.5rem", color="#a8a29e")
    ui.html(
      "<p class='text-center text-[#625E57] text-sm leading-relaxed max-w-lg m-0' style='font-family:Georgia,serif'>"
      "Análisis gemológico no requerido para esta disciplina. "
      "Utilice el interruptor superior si desea habilitar el laboratorio interactivo."
      "</p>"
    )


def render_jewelry_cad_laboratory(
  *,
  saved_cad: dict,
  can_save: bool,
  on_apply_cad: Callable[[], None],
  cad_payload_holder: dict | None = None,
) -> None:
  """Plano técnico interactivo (joyería) — pestaña II."""
  ui.html(
    "<span class='micro-coord text-[#141413]'>"
    "/// PLANO TÉCNICO INTERACTIVO"
    "</span>"
  )

  cad_type = ui.select(
    _ui_options(JEWELRY_TYPES),
    value=saved_cad.get("jewelry_type", "Anillo / Sortija"),
    label="1. Tipología de pieza",
  ).classes("w-full")

  with ui.row().classes("w-full grid grid-cols-1 sm:grid-cols-2 gap-3"):
    cad_shank = ui.select(
      _ui_options(RING_SHANK_PROFILES),
      value=saved_cad.get("shank_profile", RING_SHANK_PROFILES[0]),
      label="2. Estilo de Anillo / Banda",
    ).classes("w-full")
    cad_setting = ui.select(
      _ui_options(SETTING_ARCHITECTURES),
      value=saved_cad.get("setting_arch", SETTING_ARCHITECTURES[0]),
      label="3. Tipo de Engaste (ver dibujo III)",
    ).classes("w-full")

  blueprint_slot = ui.column().classes("w-full gap-1")

  ui.html("<span class='micro-coord mt-1'>COTAS DE MONTURA Y METAL (SEGÚN EL PLANO SUPERIOR)</span>")
  with ui.row().classes("w-full grid grid-cols-2 sm:grid-cols-3 gap-2"):
    cad_weight = ui.input(
      label="Peso total (g)",
      value=str(saved_cad.get("weight_g", "")),
      placeholder="Ej. 5.4",
    ).classes("w-full")
    cad_a = ui.input(
      label="Cota A: Ø Int (mm)",
      value=str(saved_cad.get("cota_a_mm", "")),
      placeholder="Ej. 17.2",
    ).classes("w-full")
    cad_b = ui.input(
      label="Cota B: Ancho Banda",
      value=str(saved_cad.get("cota_b_mm", "")),
      placeholder="Ej. 3.8",
    ).classes("w-full")
    cad_c = ui.input(
      label="Cota C: Espesor Aro",
      value=str(saved_cad.get("cota_c_mm", "")),
      placeholder="Ej. 1.6",
    ).classes("w-full")
    cad_d = ui.input(
      label="Cota D: Alt. Cabeza",
      value=str(saved_cad.get("cota_d_mm", "")),
      placeholder="Ej. 6.5",
    ).classes("w-full")

  ui.html("<span class='micro-coord mt-2'>COTA E // PIEDRA PRINCIPAL O SERIE 1 (EJ. ESMERALDAS)</span>")
  with ui.row().classes("w-full grid grid-cols-3 gap-2"):
    c_species = ui.select(
      list(SPECIES_DENSITY_MULTIPLIER.keys()),
      value=saved_cad.get("central_species", "Esmeralda"),
      label="Especie",
    ).classes("w-full")
    c_cut = ui.select(
      _ui_options(GEM_CUT_CATALOG),
      value=saved_cad.get("central_cut", "Esmeralda / Octogonal"),
      label="Corte / Talla",
    ).classes("w-full")
    c_count = ui.number(
      label="Cantidad",
      value=int(saved_cad.get("central_count", 1)),
      min=0,
      step=1,
    ).classes("w-full")
  with ui.row().classes("w-full grid grid-cols-3 gap-2"):
    c_l = ui.number(
      label="Largo (mm)",
      value=float(saved_cad.get("central_l_mm", 0.0)),
      min=0.0,
      step=0.1,
    ).classes("w-full")
    c_w = ui.number(
      label="Ancho (mm)",
      value=float(saved_cad.get("central_w_mm", 0.0)),
      min=0.0,
      step=0.1,
    ).classes("w-full")
    c_d = ui.number(
      label="Prof. (mm)",
      value=float(saved_cad.get("central_d_mm", 0.0)),
      min=0.0,
      step=0.1,
    ).classes("w-full")

  ui.html("<span class='micro-coord mt-2'>COTA F // PIEDRAS SECUNDARIAS / HOMBROS / SERIE 2 (EJ. DIAMANTES)</span>")
  with ui.row().classes("w-full grid grid-cols-3 gap-2"):
    s_species = ui.select(
      list(SPECIES_DENSITY_MULTIPLIER.keys()),
      value=saved_cad.get("side_species", "Diamante"),
      label="Especie",
    ).classes("w-full")
    s_cut = ui.select(
      _ui_options(GEM_CUT_CATALOG),
      value=saved_cad.get("side_cut", "Brillante Redondo"),
      label="Corte / Talla",
    ).classes("w-full")
    s_count = ui.number(
      label="Cantidad real",
      value=int(saved_cad.get("side_count", 0)),
      min=0,
      step=1,
    ).classes("w-full")
  with ui.row().classes("w-full grid grid-cols-2 gap-2"):
    s_l = ui.number(
      label="Largo / Ø (mm)",
      value=float(saved_cad.get("side_l_mm", 0.0)),
      min=0.0,
      step=0.1,
    ).classes("w-full")
    s_w = ui.number(
      label="Ancho (mm)",
      value=float(saved_cad.get("side_w_mm", 0.0)),
      min=0.0,
      step=0.1,
    ).classes("w-full")

  carat_preview = ui.label("").classes("micro-coord text-[#141413] mt-1")

  def refresh_cad_visuals() -> None:
    blueprint_slot.clear()
    total_ring_stones = int(c_count.value or 0) + int(s_count.value or 0)
    with blueprint_slot:
      ui.html(
        _dynamic_blueprint_svg_html(
          cad_type.value,
          cad_shank.value,
          cad_setting.value,
          c_cut.value,
          s_cut.value,
          total_ring_stones if "alianza" in (cad_shank.value or "").lower() else int(s_count.value or 0),
        )
      )
      guide_txt = _plain_language_measurement_guide(cad_shank.value, cad_setting.value)
      ui.html(
        f"<p class='text-[11px] text-[#625E57] leading-snug m-0 px-1'>"
        f"💡 <strong>Guía visual:</strong> {html.escape(guide_txt)}</p>"
      )

    ct_c = estimate_carats_from_mm(
      c_species.value,
      c_cut.value,
      int(c_count.value or 0),
      float(c_l.value or 0),
      float(c_w.value or 0),
      float(c_d.value or 0),
    )
    ct_s = estimate_carats_from_mm(
      s_species.value,
      s_cut.value,
      int(s_count.value or 0),
      float(s_l.value or 0),
      float(s_w.value or 0),
      0.0,
    )
    tot = round(ct_c + ct_s, 3)
    carat_preview.text = (
      f"QUILATAJE GEOMÉTRICO CALCULADO: SERIE 1 ({ct_c} CT) + SERIE 2 ({ct_s} CT) = TOTAL {tot} CT"
    )

  for ctrl in (
    cad_type,
    cad_shank,
    cad_setting,
    c_species,
    c_cut,
    c_count,
    c_l,
    c_w,
    c_d,
    s_species,
    s_cut,
    s_count,
    s_l,
    s_w,
  ):
    ctrl.on_value_change(lambda _: refresh_cad_visuals())
  refresh_cad_visuals()

  cad_hyp = ui.select(
    [
      "Evaluar Ambas Hipótesis (Gema Natural vs. Sintética)",
      "Confirmado en joyería: Gemas Naturales",
      "Confirmado en joyería: Sintéticas / Simulantes",
      "Pendiente de checkeo en joyería",
    ],
    value=saved_cad.get(
      "gem_hypothesis",
      "Evaluar Ambas Hipótesis (Gema Natural vs. Sintética)",
    ),
    label="Hipótesis / Resultado de Checkeo",
  ).classes("w-full")

  cad_obs = ui.input(
    label="Notas adicionales de taller / cuños",
    value=saved_cad.get("extra_observations", ""),
    placeholder="Ej. 7 esmeraldas y 5 diamantes verificados en mano...",
  ).classes("w-full")

  def build_cad_payload() -> dict:
    ct_c = estimate_carats_from_mm(
      c_species.value,
      c_cut.value,
      int(c_count.value or 0),
      float(c_l.value or 0),
      float(c_w.value or 0),
      float(c_d.value or 0),
    )
    ct_s = estimate_carats_from_mm(
      s_species.value,
      s_cut.value,
      int(s_count.value or 0),
      float(s_l.value or 0),
      float(s_w.value or 0),
      0.0,
    )
    return {
      "jewelry_type": cad_type.value,
      "shank_profile": cad_shank.value,
      "setting_arch": cad_setting.value,
      "weight_g": (cad_weight.value or "").strip(),
      "cota_a_mm": (cad_a.value or "").strip(),
      "cota_b_mm": (cad_b.value or "").strip(),
      "cota_c_mm": (cad_c.value or "").strip(),
      "cota_d_mm": (cad_d.value or "").strip(),
      "central_species": c_species.value,
      "central_cut": c_cut.value,
      "central_count": int(c_count.value or 0),
      "central_l_mm": float(c_l.value or 0),
      "central_w_mm": float(c_w.value or 0),
      "central_d_mm": float(c_d.value or 0),
      "central_ct": ct_c,
      "side_species": s_species.value,
      "side_cut": s_cut.value,
      "side_count": int(s_count.value or 0),
      "side_l_mm": float(s_l.value or 0),
      "side_w_mm": float(s_w.value or 0),
      "side_ct": ct_s,
      "total_ct": round(ct_c + ct_s, 3),
      "gem_hypothesis": cad_hyp.value,
      "extra_observations": (cad_obs.value or "").strip(),
    }

  if cad_payload_holder is not None:
    cad_payload_holder["build"] = build_cad_payload

  if can_save:
    editorial_button("RECALCULAR CON COTAS CAD Y GEMAS", on_click=on_apply_cad)


def _physical_metrology_rows(case_data: dict) -> list[tuple[str, str]]:
    """Filas de cotas/peso con dato presente; vacío si no hay nada que mostrar."""
    dims = forensic_dimensions_dict(case_data)
    cad = case_data.get("cad_blueprint") if isinstance(case_data.get("cad_blueprint"), dict) else {}
    peso = resolve_mass_grams(case_data)

    def _dim(key_forensic: str, *cad_keys: str) -> str:
        if dims.get(key_forensic) not in (None, ""):
            return str(dims[key_forensic])
        for ck in cad_keys:
            if cad.get(ck) not in (None, "", 0):
                return str(cad[ck])
        return ""

    rows = [
        ("Cota X (mm)", _dim("length", "cota_x_mm", "length_mm", "cota_b_mm")),
        ("Cota Y (mm)", _dim("width", "cota_y_mm", "width_mm", "cota_a_mm")),
        ("Cota Z (mm)", _dim("height", "cota_z_mm", "height_mm", "cota_d_mm", "cota_c_mm")),
        ("Peso total (g)", peso),
    ]
    return [(label, value) for label, value in rows if spec_value_is_present(value)]


def render_physical_metrology_block(case_data: dict) -> None:
    """Metrología genérica: solo cotas y peso verificados; sin bloque si no hay datos."""
    visible = _physical_metrology_rows(case_data)
    if not visible:
        return

    with ui.column().classes("human-evidence-box w-full gap-3"):
        ui.html(
            "<span class='micro-coord text-[#141413]'>"
            "/// METROLOGÍA Y COTAS FÍSICAS"
            "</span>"
        )
        rows_html = "".join(
            f"<div class='spec-row'><span class='spec-label'>{html.escape(label)}</span>"
            f"<span class='spec-value'>{html.escape(str(value))}</span></div>"
            for label, value in visible
        )
        ui.html(f"<div class='spec-table w-full'>{rows_html}</div>")


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
                subj_radio = ui.radio(
                    _ui_options(SUBJECTS),
                    value=gem_state["subject"],
                ).props("inline dense color=dark")
                subj_radio.on_value_change(lambda e: (gem_state.update({"subject": e.value}), render_controls()))

                with ui.row().classes("w-full grid grid-cols-1 sm:grid-cols-2 gap-4"):
                    ui.select(_ui_options(METALS), value=gem_state["metal_kind"], label="Metal base").on_value_change(
                        lambda e: (gem_state.update({"metal_kind": e.value}), render_controls())
                    ).classes("w-full")
                    ui.number(label="Gramos de metal", value=gem_state["metal_grams"], min=0.0, step=0.1).on_value_change(
                        lambda e: (gem_state.update({"metal_grams": float(e.value or 0.0)}), render_controls())
                    ).classes("w-full")
                    ui.select(_ui_options(AUTHORSHIPS), value=gem_state["authorship"], label="Autoría o taller").on_value_change(
                        lambda e: (gem_state.update({"authorship": e.value}), render_controls())
                    ).classes("w-full")
                    ui.select(_ui_options(SETTINGS), value=gem_state["setting"], label="Engaste").on_value_change(
                        lambda e: (gem_state.update({"setting": e.value}), render_controls())
                    ).classes("w-full")

                if gem_state["subject"] in ("Gema", "Gema y perla"):
                    ui.html("<span class='micro-coord mt-2'>PARÁMETROS DE GEMA</span>")
                    with ui.row().classes("w-full grid grid-cols-1 sm:grid-cols-3 gap-3"):
                        ui.select(_ui_options(GEM_SPECIES), value=gem_state["gem"]["species"], label="Especie").on_value_change(
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
                        ui.select(_ui_options(GEM_COLORS), value=gem_state["gem"]["color"], label="Color").on_value_change(
                            lambda e: (gem_state["gem"].update({"color": e.value}), render_controls())
                        ).classes("w-full")
                        ui.select(
                            _ui_options(GEM_CLARITIES),
                            value=gem_state["gem"]["clarity"],
                            label="Pureza",
                        ).on_value_change(
                            lambda e: (gem_state["gem"].update({"clarity": e.value}), render_controls())
                        ).classes("w-full")
                        ui.select(_ui_options(GEM_CUTS), value=gem_state["gem"]["cut"], label="Talla").on_value_change(
                            lambda e: (gem_state["gem"].update({"cut": e.value}), render_controls())
                        ).classes("w-full")
                        ui.select(
                            _ui_options(GEM_NATURES),
                            value=gem_state["gem"]["nature"],
                            label="Naturaleza",
                        ).on_value_change(
                            lambda e: (gem_state["gem"].update({"nature": e.value}), render_controls())
                        ).classes("w-full")

                if gem_state["subject"] in ("Perla", "Gema y perla"):
                    ui.html("<span class='micro-coord mt-2'>PARÁMETROS DE PERLA</span>")
                    with ui.row().classes("w-full grid grid-cols-1 sm:grid-cols-3 gap-3"):
                        ui.select(
                            _ui_options(PEARL_NATURES),
                            value=gem_state["pearl"]["nature"],
                            label="Naturaleza",
                        ).on_value_change(
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
                        ui.select(
                            _ui_options(PEARL_LUSTER),
                            value=gem_state["pearl"]["luster"],
                            label="Lustre",
                        ).on_value_change(
                            lambda e: (gem_state["pearl"].update({"luster": e.value}), render_controls())
                        ).classes("w-full")
                        ui.select(_ui_options(PEARL_NACRE), value=gem_state["pearl"]["nacre"], label="Nácar").on_value_change(
                            lambda e: (gem_state["pearl"].update({"nacre": e.value}), render_controls())
                        ).classes("w-full")
                        ui.select(
                            _ui_options(PEARL_SURFACE),
                            value=gem_state["pearl"]["surface"],
                            label="Superficie",
                        ).on_value_change(
                            lambda e: (gem_state["pearl"].update({"surface": e.value}), render_controls())
                        ).classes("w-full")
                        ui.select(
                            _ui_options(PEARL_MATCHING),
                            value=gem_state["pearl"]["matching"],
                            label="Matching",
                        ).on_value_change(
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