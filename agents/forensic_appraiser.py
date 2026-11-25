"""Agente forense universal con biblioteca evolutiva de protocolos (cloud)."""

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
from PIL import Image
from pydantic import ValidationError

from agents.forensic_prompts import (
    DOUBLE_BRAIN_DIRECTIVE,
    FORENSIC_JSON_ACTIONABLE_FIELDS,
    FORENSIC_JSON_AUDIT_TRAIL_FIELDS,
    FORENSIC_JSON_RESOLVED_FIELDS,
    FORENSIC_JSON_SERIAL_FIELDS,
    GLOBAL_AUDIT_TRAIL_DIRECTIVE,
    RESOLVED_REQUESTS_DIRECTIVE,
    SERIAL_DECODING_DIRECTIVE,
    VISUAL_ANCHORING_DIRECTIVE,
)
from agents.schemas import (
    ForensicReport,
    SynthesizedRubric,
    TaxonomyGuess,
    infer_parent_domain,
    normalize_snake_key,
)
from database.client import (
    _merge_unique_strings,
    get_domain_rubric,
    list_existing_rubrics_summary,
    list_rubrics_by_parent_domain,
    upsert_domain_rubric,
)

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _forensic_log(step: str) -> None:
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


def _parse_model_json(raw: str, model_cls):
    payload = json.loads(_strip_json_fence(raw))
    return model_cls.model_validate(payload)


class UniversalForensicAgent:
    """Consulta o sintetiza protocolos por taxonomía y ejecuta peritaje multimodal."""

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

    def appraise(
        self,
        object_description: str,
        context_notes: str = "",
        image_paths: list | None = None,
        case_id: str = "DEFAULT",
    ) -> ForensicReport | None:
        if not self.client:
            _forensic_log("[FORENSE] Sin cliente Gemini; se omite peritaje estructurado.")
            return None

        usable = [p for p in (image_paths or []) if p and os.path.exists(p)]
        _forensic_log("[FORENSE A] Identificando taxonomía disciplinar de la pieza…")
        taxonomy = self._identify_taxonomy(object_description, context_notes, usable, case_id)
        if taxonomy is None:
            _forensic_log("[FORENSE A] No se pudo inferir taxonomía; abortando peritaje estructurado.")
            return None

        reuse_tag = "reutilizada" if taxonomy.reuses_existing_key else "nueva/especializada"
        _forensic_log(
            f"[FORENSE A] Taxonomía ({reuse_tag}): {taxonomy.taxonomy_key} "
            f"· familia {taxonomy.parent_domain} · {taxonomy.display_name}"
        )
        rubric = self._load_or_synthesize_rubric(taxonomy, object_description, context_notes, usable)

        _forensic_log("[FORENSE B] Peritaje multimodal con protocolo vigente…")
        t0 = time.perf_counter()
        report = self._run_forensic_analysis(
            taxonomy.taxonomy_key,
            taxonomy.display_name,
            taxonomy.category_name,
            object_description,
            context_notes,
            rubric,
            usable,
            case_id,
        )
        _forensic_log(f"[FORENSE B] Peritaje listo ({time.perf_counter() - t0:.1f}s)")

        if report and report.new_protocol_insights:
            _forensic_log(
                f"[FORENSE B] Fusionando {len(report.new_protocol_insights)} insight(s) en biblioteca…"
            )
            upsert_domain_rubric(
                {
                    "taxonomy_key": report.taxonomy_key,
                    "parent_domain": taxonomy.parent_domain,
                    "display_name": taxonomy.display_name,
                    "inspection_checklist": report.new_protocol_insights,
                    "authenticity_red_flags": report.anomalies_detected,
                    "cad_measurement_guide": rubric.get("cad_measurement_guide") or "",
                }
            )
        return report

    def _load_or_synthesize_rubric(
        self,
        taxonomy: TaxonomyGuess,
        object_description: str,
        context_notes: str,
        image_paths: list,
    ) -> dict:
        stored = get_domain_rubric(taxonomy.taxonomy_key)
        if stored is not None:
            _forensic_log(
                f"[FORENSE A] Protocolo en biblioteca v{stored.version} recuperado."
            )
            rubric = {
                "taxonomy_key": normalize_snake_key(stored.taxonomy_key),
                "parent_domain": normalize_snake_key(
                    stored.parent_domain or taxonomy.parent_domain
                ),
                "display_name": stored.display_name,
                "version": stored.version,
                "inspection_checklist": list(stored.inspection_checklist or []),
                "authenticity_red_flags": list(stored.authenticity_red_flags or []),
                "cad_measurement_guide": stored.cad_measurement_guide or "",
            }
            rubric.update(self._family_rubric_context(rubric["parent_domain"], rubric["taxonomy_key"]))
            return rubric

        _forensic_log("[FORENSE A] Taxonomía inédita · sintetizando rúbrica inicial…")
        synthesized = self._synthesize_rubric(
            taxonomy, object_description, context_notes, image_paths
        )
        if synthesized is None:
            fallback = {
                "taxonomy_key": taxonomy.taxonomy_key,
                "parent_domain": taxonomy.parent_domain,
                "display_name": taxonomy.display_name,
                "inspection_checklist": [],
                "authenticity_red_flags": [],
                "cad_measurement_guide": "",
            }
            fallback.update(self._family_rubric_context(taxonomy.parent_domain, taxonomy.taxonomy_key))
            return fallback

        payload = synthesized.model_dump()
        payload["parent_domain"] = taxonomy.parent_domain
        upsert_domain_rubric(payload)
        _forensic_log("[FORENSE A] Rúbrica nueva persistida en PostgreSQL.")
        payload.update(self._family_rubric_context(taxonomy.parent_domain, taxonomy.taxonomy_key))
        return payload

    def _family_rubric_context(self, parent_domain: str, exclude_taxonomy_key: str) -> dict:
        parent = normalize_snake_key(parent_domain)
        exclude = normalize_snake_key(exclude_taxonomy_key)
        siblings = list_rubrics_by_parent_domain(parent)
        family_checklist: list[str] = []
        family_flags: list[str] = []
        family_guides: list[str] = []
        sibling_labels: list[str] = []
        for sibling in siblings:
            sib_key = normalize_snake_key(sibling.taxonomy_key)
            if sib_key == exclude:
                continue
            sibling_labels.append(f"{sib_key} ({sibling.display_name})")
            family_checklist.extend(list(sibling.inspection_checklist or []))
            family_flags.extend(list(sibling.authenticity_red_flags or []))
            guide = (sibling.cad_measurement_guide or "").strip()
            if guide:
                family_guides.append(guide)
        if siblings:
            _forensic_log(
                f"[FORENSE A] Herencia familiar {parent}: {len(sibling_labels)} rúbrica(s) hermana(s) fusionadas."
            )
        return {
            "family_parent_domain": parent,
            "family_sibling_rubrics": sibling_labels,
            "family_inspection_checklist": _merge_unique_strings([], family_checklist),
            "family_authenticity_red_flags": _merge_unique_strings([], family_flags),
            "family_cad_guides": family_guides,
        }

    def _identify_taxonomy(
        self,
        object_description: str,
        context_notes: str,
        image_paths: list,
        case_id: str,
    ) -> TaxonomyGuess | None:
        catalog = list_existing_rubrics_summary()
        catalog_lines = [
            f"- {row['taxonomy_key']} | familia={row['parent_domain']} | {row['display_name']} | v{row['version']}"
            for row in catalog
        ]
        catalog_text = "\n".join(catalog_lines) if catalog_lines else "(biblioteca vacía)"

        system = (
            "Eres el arquitecto taxonómico forense CH. Tu misión es REUTILIZAR protocolos existentes antes de inventar claves nuevas. "
            "Devuelve SOLO JSON TaxonomyGuess con: taxonomy_key, parent_domain, display_name, category_name, rationale, reuses_existing_key (bool). "
            "REGLAS ESTRICTAS:\n"
            "1) taxonomy_key y parent_domain SIEMPRE en UPPER_SNAKE_CASE ASCII (sin tildes).\n"
            "2) parent_domain es la familia padre corta (ej. RELOJERIA, DESTILADOS, JOYERIA, FILATELIA).\n"
            "3) Si la pieza pertenece a la misma especialidad que una taxonomy_key existente (misma inspección física y geometría CAD), "
            "DEBES devolver exactamente esa taxonomy_key existente con reuses_existing_key=true.\n"
            "4) Crea una taxonomy_key NUEVA solo si las reglas de inspección física o la geometría CAD cambian sustancialmente "
            "(ej. reloj de sobremesa vs. reloj de pulsera), pero con el mismo parent_domain (ej. ambos RELOJERIA).\n"
            "5) No dupliques familias por diferencias de redacción: unifica bajo la clave existente más específica compatible."
        )
        prompt = (
            f"Caso {case_id}\n"
            f"Descripción operativa: {object_description}\n"
            f"Notas del perito: {context_notes}\n\n"
            f"=== RÚBRICAS EXISTENTES EN POSTGRESQL ===\n{catalog_text}\n\n"
            "Triaje: reutiliza taxonomy_key existente o propone una nueva especializada con parent_domain coherente."
        )
        raw = self._generate_json(system, prompt, image_paths)
        if not raw:
            return None
        try:
            guess = _parse_model_json(raw, TaxonomyGuess)
            return self._reconcile_taxonomy_guess(guess, catalog)
        except (json.JSONDecodeError, ValidationError) as exc:
            _forensic_log(f"[FORENSE A] JSON taxonomía inválido: {exc}")
            return None

    def _reconcile_taxonomy_guess(self, guess: TaxonomyGuess, catalog: list[dict]) -> TaxonomyGuess:
        canonical_key = normalize_snake_key(guess.taxonomy_key)
        parent = normalize_snake_key(guess.parent_domain or infer_parent_domain(canonical_key))
        by_key = {row["taxonomy_key"]: row for row in catalog}

        if canonical_key in by_key:
            row = by_key[canonical_key]
            return guess.model_copy(
                update={
                    "taxonomy_key": row["taxonomy_key"],
                    "parent_domain": row["parent_domain"],
                    "reuses_existing_key": True,
                }
            )

        if guess.reuses_existing_key and catalog:
            parent_rows = [row for row in catalog if row["parent_domain"] == parent]
            if len(parent_rows) == 1:
                row = parent_rows[0]
                _forensic_log(
                    f"[FORENSE A] Reutilización forzada → {row['taxonomy_key']} (única clave en familia {parent})."
                )
                return guess.model_copy(
                    update={
                        "taxonomy_key": row["taxonomy_key"],
                        "parent_domain": row["parent_domain"],
                        "reuses_existing_key": True,
                    }
                )

        return guess.model_copy(
            update={
                "taxonomy_key": canonical_key,
                "parent_domain": parent,
            }
        )

    def _synthesize_rubric(
        self,
        taxonomy: TaxonomyGuess,
        object_description: str,
        context_notes: str,
        image_paths: list,
    ) -> SynthesizedRubric | None:
        system = (
            "Eres arquitecto de protocolos forenses universales. Genera una rúbrica completa para la taxonomía "
            "indicada sin suponer otra disciplina. Devuelve SOLO JSON válido SynthesizedRubric con: taxonomy_key, "
            "parent_domain, display_name, inspection_checklist (lista de strings), authenticity_red_flags (lista), "
            "cad_measurement_guide (texto con vistas y cotas que el plano CAD debe proyectar para esta disciplina).\n\n"
            f"{VISUAL_ANCHORING_DIRECTIVE}\n"
            "Cada ítem de inspection_checklist y authenticity_red_flags debe ser una nota de auditoría visual anclada "
            "(sin preguntas ni interrogantes)."
        )
        prompt = (
            f"Taxonomía: {taxonomy.taxonomy_key} — familia {taxonomy.parent_domain} — {taxonomy.display_name}\n"
            f"Categoría pieza: {taxonomy.category_name}\n"
            f"Objeto: {object_description}\n"
            f"Notas: {context_notes}\n"
        )
        raw = self._generate_json(system, prompt, image_paths)
        if not raw:
            return None
        try:
            rubric = _parse_model_json(raw, SynthesizedRubric)
            if rubric.taxonomy_key != taxonomy.taxonomy_key:
                rubric = rubric.model_copy(update={"taxonomy_key": taxonomy.taxonomy_key})
            if not rubric.display_name:
                rubric = rubric.model_copy(update={"display_name": taxonomy.display_name})
            rubric = rubric.model_copy(update={"parent_domain": taxonomy.parent_domain})
            return rubric
        except (json.JSONDecodeError, ValidationError) as exc:
            _forensic_log(f"[FORENSE A] JSON rúbrica inválido: {exc}")
            return None

    def _run_forensic_analysis(
        self,
        taxonomy_key: str,
        display_name: str,
        category_name: str,
        object_description: str,
        context_notes: str,
        rubric: dict,
        image_paths: list,
        case_id: str,
    ) -> ForensicReport | None:
        checklist = _merge_unique_strings(
            rubric.get("family_inspection_checklist"),
            rubric.get("inspection_checklist"),
        )
        red_flags = _merge_unique_strings(
            rubric.get("family_authenticity_red_flags"),
            rubric.get("authenticity_red_flags"),
        )
        cad_guide = rubric.get("cad_measurement_guide") or ""
        family_guides = rubric.get("family_cad_guides") or []
        family_parent = rubric.get("family_parent_domain") or ""
        family_siblings = rubric.get("family_sibling_rubrics") or []

        system = (
            "Eres perito forense universal CH. Aplica estrictamente el protocolo disciplinar entregado. "
            "No inventes categorías fuera de la taxonomía dada. Devuelve SOLO JSON ForensicReport con todos los campos, "
            "incluyendo dimensions_mm (length, width, height, diameter en mm o null), "
            "new_protocol_insights solo si descubres criterios técnicos nuevos transferibles a futuros casos.\n\n"
            f"{SERIAL_DECODING_DIRECTIVE}\n\n"
            f"{FORENSIC_JSON_SERIAL_FIELDS}\n\n"
            f"{DOUBLE_BRAIN_DIRECTIVE}\n\n"
            f"{FORENSIC_JSON_ACTIONABLE_FIELDS}\n\n"
            f"{GLOBAL_AUDIT_TRAIL_DIRECTIVE}\n\n"
            f"{FORENSIC_JSON_AUDIT_TRAIL_FIELDS}\n\n"
            f"{RESOLVED_REQUESTS_DIRECTIVE}\n\n"
            f"{FORENSIC_JSON_RESOLVED_FIELDS}\n\n"
            f"{VISUAL_ANCHORING_DIRECTIVE}\n"
            "Usa anomalies_detected y new_protocol_insights solo para hallazgos técnicos; "
            "las peticiones al usuario van en recomendaciones (ActionableRequest), nunca mezclando varias peticiones en un solo user_prompt. "
            "El impacto económico y de confianza solo en global_audit_trail."
        )
        prompt = (
            f"Caso {case_id}\n"
            f"Taxonomía: {taxonomy_key} ({display_name})\n"
            f"Categoría: {category_name}\n"
            f"Objeto: {object_description}\n"
            f"Notas perito: {context_notes}\n\n"
            f"=== INSPECTION CHECKLIST ===\n" + "\n".join(f"- {x}" for x in checklist) + "\n\n"
            f"=== RED FLAGS ===\n" + "\n".join(f"- {x}" for x in red_flags) + "\n\n"
            f"=== GUÍA CAD (subcategoría) ===\n{cad_guide}\n\n"
            f"=== ESTÁNDARES FAMILIA {family_parent} (hermanas: {', '.join(family_siblings) or '—'}) ===\n"
            + "\n".join(f"---\n{block}" for block in family_guides)
            + "\n"
        )
        raw = self._generate_json(system, prompt, image_paths)
        if not raw:
            return None
        repair_suffix = ""
        for attempt in range(2):
            try:
                report = _parse_model_json(raw, ForensicReport)
                if report.taxonomy_key != taxonomy_key:
                    report = report.model_copy(update={"taxonomy_key": taxonomy_key})
                if not report.category_name:
                    report = report.model_copy(update={"category_name": category_name or display_name})
                return report
            except json.JSONDecodeError as exc:
                _forensic_log(f"[FORENSE B] JSON informe inválido: {exc}")
                return None
            except ValidationError as exc:
                if attempt == 0:
                    repair_suffix = (
                        f"\n\n=== CORRECCIÓN OBLIGATORIA (validación esquema) ===\n{exc}\n"
                        "Si has_factory_serial=true, serial_decoding debe incluir los cuatro campos "
                        "y serial_authenticity_impact debe contener valida, contradice o indeterminado. "
                        "recomendaciones debe ser lista de ActionableRequest válidos (un user_prompt = una petición)."
                    )
                    raw = self._generate_json(system, prompt + repair_suffix, image_paths)
                    if not raw:
                        _forensic_log(f"[FORENSE B] Informe no cumple esquema: {exc}")
                        return None
                    continue
                _forensic_log(f"[FORENSE B] Informe no cumple esquema: {exc}")
                return None
        return None

    def _generate_json(self, system_instruction: str, prompt: str, image_paths: list) -> str | None:
        contents: list = []
        for path in image_paths:
            try:
                contents.append(Image.open(path))
            except Exception as exc:
                _forensic_log(f"[FORENSE] Imagen omitida {path}: {exc}")
        contents.append(prompt)

        for attempt in range(3):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.15,
                        response_mime_type="application/json",
                    ),
                )
                return (response.text or "").strip()
            except Exception as exc:
                _forensic_log(f"[FORENSE] Inferencia JSON intento {attempt + 1}: {exc}")
                time.sleep(2 * (attempt + 1))
        return None