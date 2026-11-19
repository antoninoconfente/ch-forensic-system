import os
import json
import time
import shutil
from datetime import datetime
import re
from pathlib import Path
from PIL import Image
from dotenv import load_dotenv
from google import genai
from google.genai import types
from src.research.web_search import WebSearchEngine
from src.research.visual_search import VisualSearchEngine
from src.research.punchmarks_db import get_punchmarks_context_for_prompt

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def resolve_gemini_api_key() -> str:
    """Lee la clave de Gemini desde el entorno ya cargado con .env."""
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return ""

CASES_DIR = os.path.join("data", "cases")
INDEX_PATH = os.path.join("data", "library_index.json")
AUDIT_LOG_PATH = os.path.join("data", "agent_audit.log")


def _pipeline_log(step: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {step}", flush=True)


def sanitize_context_notes(raw_notes: str) -> str:
    """Quita bloques entre corchetes y deja un texto plano, sin cadenas acumuladas."""
    if not raw_notes:
        return ""
    text = str(raw_notes)
    for _ in range(8):
        stripped = re.sub(r"\[[^\[\]]*\]", "", text)
        if stripped == text:
            break
        text = stripped
    text = re.sub(r"[\[\]]", "", text)
    text = re.sub(r"(?i)validaci[oó]n pericial\s*:?\s*", "", text)
    text = re.sub(r"(?i)\bspot market data\b.{0,200}", "", text)
    text = re.sub(r"(?i)\baclaraci[oó]n\s*:?\s*", "", text)
    text = re.sub(r"[|]+", ". ", text)
    text = re.sub(r"\s*[—–]+\s*", ". ", text)
    text = re.sub(r"\s+", " ", text).strip(" .-")
    return text


def _split_legacy_context_notes(context_notes: str) -> tuple[str, list]:
    """Separa el prefijo original de los fragmentos de respuesta unidos por ';'."""
    text = (context_notes or "").strip()
    if not text or text == "Sin notas adicionales":
        return "", []
    if ". " in text:
        base, rest = text.split(". ", 1)
        parts = [part.strip() for part in rest.split(";") if part.strip()]
        return base.strip(), parts
    if ";" in text:
        parts = [part.strip() for part in text.split(";") if part.strip()]
        return "", parts
    return text, []


def _compose_context_notes(intake_notes: str, question_answers: dict) -> str:
    """Texto de trabajo para el modelo. No es la ficha persistida."""
    lines = []
    base = sanitize_context_notes(intake_notes or "")
    if base and base != "Sin notas adicionales":
        lines.append(f"Ingreso: {base}")
    for key, value in (question_answers or {}).items():
        if str(key).startswith("__legacy_"):
            continue
        answer = "" if value is None else str(value).strip()
        if not answer or answer.lower() in {"pendiente", "n/a", "na", "—", "-"}:
            continue
        lines.append(f"Pregunta: {key}\nRespuesta: {answer}")
    return "\n".join(lines)


def apply_interrogation_update(existing_metadata: dict, pending_questions: list, answers_by_index: dict) -> dict:
    """Sustituye la respuesta de cada cuestión por el input actual. Un campo en blanco queda vacío."""
    metadata = existing_metadata or {}
    answers = {str(key): str(value or "") for key, value in (metadata.get("question_answers") or {}).items()}
    intake = metadata.get("intake_notes")
    if intake is None:
        intake, legacy_parts = _split_legacy_context_notes(metadata.get("context_notes", ""))
        if not answers and legacy_parts and pending_questions:
            start = max(0, len(legacy_parts) - len(pending_questions))
            for offset, part in enumerate(legacy_parts[:start]):
                answers[f"__legacy_{offset}"] = part
            for offset, question in enumerate(pending_questions):
                if start + offset < len(legacy_parts):
                    answers[question] = legacy_parts[start + offset]
        elif not answers and legacy_parts:
            for offset, part in enumerate(legacy_parts):
                answers[f"__legacy_{offset}"] = part

    for index, question in enumerate(pending_questions or []):
        raw = answers_by_index.get(index, "")
        answers[str(question)] = raw.strip() if isinstance(raw, str) else ""

    return {
        "intake_notes": intake or "",
        "question_answers": answers,
        "context_notes": intake or "",
        "prompt_context": _compose_context_notes(intake or "", answers),
    }


def case_label(record: dict) -> str:
    """Nombre visible de la ficha. No usa el volcado concatenado de respuestas."""
    if not record:
        return "Ficha Técnica"
    intake = str(record.get("intake_notes") or "").strip()
    if intake and intake != "Sin notas adicionales":
        return intake
    description = str(record.get("object_description") or "").strip()
    notes = str(record.get("context_notes") or "").strip()
    flat_dump = ";" in notes or "\nPregunta:" in notes
    if description and "analizada por visión" not in description:
        return description
    if notes and not flat_dump and notes != "Sin notas adicionales" and "analizada por visión" not in notes:
        return notes
    if "analizada por visión" in description or "analizada por visión" in notes:
        return "Ficha Técnica"
    return description or "Ficha Técnica"


def relationalize_metadata(metadata: dict) -> dict:
    """Convierte un volcado plano heredado en campos separados, sin reescribirlo como cadena."""
    record = dict(metadata or {})
    answers = record.get("question_answers")
    notes = str(record.get("context_notes") or "")
    if answers or ";" not in notes:
        return record
    intake, parts = _split_legacy_context_notes(notes)
    record["intake_notes"] = record.get("intake_notes") or intake
    record["question_answers"] = {f"__legacy_{index}": part for index, part in enumerate(parts)}
    record["context_notes"] = record.get("intake_notes") or ""
    return record


def index_entry_from_metadata(metadata: dict, folder_path: str) -> dict:
    """Copia el expediente al índice sin unir respuestas en una sola cadena."""
    stored_answers = metadata.get("question_answers") or {}
    resolved = metadata.get("resolved_questions") or []
    notes = str(metadata.get("intake_notes") or "")
    raw_notes = str(metadata.get("context_notes") or "")
    if not notes and ";" not in raw_notes and "\nPregunta:" not in raw_notes:
        notes = raw_notes
    return {
        "case_id": metadata.get("case_id"),
        "object_description": metadata.get("object_description", ""),
        "intake_notes": metadata.get("intake_notes", ""),
        "question_answers": stored_answers if isinstance(stored_answers, dict) else {},
        "resolved_questions": resolved if isinstance(resolved, list) else [],
        "context_notes": notes,
        "image_path": metadata.get("image_path"),
        "folder_path": folder_path,
        "status": metadata.get("status", "active"),
        "logistics_intelligence": metadata.get("logistics_intelligence") or {},
        "gemology_data": metadata.get("gemology_data") or {},
    }


class CastleLibrary:
    @staticmethod
    def _ensure_storage():
        os.makedirs(CASES_DIR, exist_ok=True)
        if not os.path.exists(INDEX_PATH):
            with open(INDEX_PATH, "w", encoding="utf-8") as f:
                json.dump({
                    "cataloged_cases": [],
                    "search_queries_log": {},
                    "trusted_domains": []
                }, f, indent=2)

    @classmethod
    def _log_audit(cls, message: str):
        try:
            os.makedirs("data", exist_ok=True)
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            print(f"Error escribiendo en audit log: {e}")

    @classmethod
    def get_index(cls) -> dict:
        cls._ensure_storage()
        try:
            with open(INDEX_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"cataloged_cases": [], "search_queries_log": {}, "trusted_domains": []}

    @classmethod
    def save_case(cls, case_id: str, object_description: str, context_notes: str, dictamen: str, image_paths: list = None, successful_queries: list = None):
        cls._ensure_storage()
        
        case_folder = os.path.join(CASES_DIR, case_id)
        evidence_folder = os.path.join(case_folder, "evidence")
        os.makedirs(evidence_folder, exist_ok=True)

        permanent_primary_image = None
        
        if image_paths:
            for i, img_p in enumerate(image_paths):
                if img_p and os.path.exists(img_p):
                    try:
                        ext = os.path.splitext(img_p)[1]
                        filename = f"evidence_{i+1}{ext}"
                        dest_path = os.path.join(evidence_folder, filename)
                        if os.path.abspath(img_p) != os.path.abspath(dest_path):
                            shutil.copy(img_p, dest_path)
                        if i == 0:
                            permanent_primary_image = dest_path
                    except Exception as e:
                        cls._log_audit(f"Error copiando evidencia {i+1} al expediente {case_id}: {e}")

        md_path = os.path.join(case_folder, "dictamen.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(dictamen)

        meta_path = os.path.join(case_folder, "metadata.json")
        existing_metadata = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as mf:
                    existing_metadata = json.load(mf)
            except Exception:
                pass

        flat_notes = sanitize_context_notes(context_notes)
        has_answer_state = "question_answers" in existing_metadata or "intake_notes" in existing_metadata
        if not flat_notes and not has_answer_state:
            flat_notes = "Sin notas adicionales"

        metadata = dict(existing_metadata)
        metadata.update({
            "case_id": case_id,
            "object_description": object_description,
            "image_path": permanent_primary_image or existing_metadata.get("image_path"),
            "dictamen_path": md_path,
            "successful_queries": successful_queries or existing_metadata.get("successful_queries", []),
            "resolved_questions": existing_metadata.get("resolved_questions", []),
            "timestamp": time.time()
        })
        if has_answer_state:
            metadata["intake_notes"] = existing_metadata.get("intake_notes", "")
            metadata["question_answers"] = existing_metadata.get("question_answers", {})
            metadata["context_notes"] = existing_metadata.get("intake_notes", "") or ""
        else:
            metadata["context_notes"] = flat_notes
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        index_data = cls.get_index()
        index_data["cataloged_cases"] = [x for x in index_data.get("cataloged_cases", []) if x.get("case_id") != case_id]
        index_data["cataloged_cases"].append(index_entry_from_metadata(metadata, case_folder))

        if successful_queries:
            base_text = metadata.get("context_notes") if metadata.get("context_notes") not in ("", "Sin notas adicionales") else object_description
            key_tag = base_text.split()[0].upper() if base_text else "GENERAL"
            
            if key_tag not in index_data["search_queries_log"]:
                index_data["search_queries_log"][key_tag] = []
            for q in successful_queries:
                if q not in index_data["search_queries_log"][key_tag]:
                    index_data["search_queries_log"][key_tag].append(q)

        with open(INDEX_PATH, "w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=2, ensure_ascii=False)

        cls._log_audit(f"Caso {case_id} guardado con éxito en {case_folder}")

    @classmethod
    def load_metadata(cls, case_id: str) -> dict:
        meta_path = os.path.join(CASES_DIR, case_id or "", "metadata.json")
        if not case_id or not os.path.exists(meta_path):
            return {}
        try:
            with open(meta_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @classmethod
    def consolidate_case(cls, case_id: str) -> bool:
        """Pasa el caso activo a ficha conservando metadatos relacionales, sin volcado plano."""
        metadata = relationalize_metadata(cls.load_metadata(case_id))
        if not metadata:
            return False
        case_folder = os.path.join(CASES_DIR, case_id)
        metadata["status"] = "consolidated"
        meta_path = os.path.join(case_folder, "metadata.json")
        with open(meta_path, "w", encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2, ensure_ascii=False)

        index_data = cls.get_index()
        index_data["cataloged_cases"] = [item for item in index_data.get("cataloged_cases", []) if item.get("case_id") != case_id]
        index_data["cataloged_cases"].append(index_entry_from_metadata(metadata, case_folder))
        with open(INDEX_PATH, "w", encoding="utf-8") as handle:
            json.dump(index_data, handle, indent=2, ensure_ascii=False)
        cls._log_audit(f"Expediente {case_id} consolidado como ficha sin aplanar metadatos.")
        return True

    @classmethod
    def get_all_cases(cls) -> list:
        index_data = cls.get_index()
        return index_data.get("cataloged_cases", [])

    @classmethod
    def get_heuristic_queries(cls, object_description: str, context_notes: str = "") -> list:
        index_data = cls.get_index()
        base_text = context_notes if (context_notes and context_notes != "Sin notas adicionales") else object_description
        key_tag = base_text.split()[0].upper() if base_text else "GENERAL"
        return index_data.get("search_queries_log", {}).get(key_tag, [])

    @classmethod
    def delete_case(cls, case_id: str) -> bool:
        try:
            case_folder = os.path.join(CASES_DIR, case_id)
            if os.path.exists(case_folder):
                shutil.rmtree(case_folder)
            
            index_data = cls.get_index()
            index_data["cataloged_cases"] = [x for x in index_data.get("cataloged_cases", []) if x.get("case_id") != case_id]
            with open(INDEX_PATH, "w", encoding="utf-8") as f:
                json.dump(index_data, f, indent=2, ensure_ascii=False)
            CastleLibrary._log_audit(f"Expediente {case_id} eliminado de la CastleLibrary.")
            return True
        except Exception as e:
            CastleLibrary._log_audit(f"Error borrando expediente {case_id}: {e}")
            return False

def clean_dictamen_for_output(raw_dictamen: str) -> tuple[str, list]:
    if not raw_dictamen:
        return "", []
    
    flag_pattern = r"\[FLAG_REQUEST_IMAGE:\s*([^\]]+)\]"
    found_flags = re.findall(flag_pattern, raw_dictamen)
    
    clean_text = re.sub(flag_pattern, "", raw_dictamen)
    clean_text = clean_text.replace("1. ⚠️ ALERTAS DE EXCEPCIÓN Y AUDITORÍA PERICIAL\nNinguna.", "").strip()
    
    return clean_text, found_flags

class LocalAIAgent:
    def __init__(self, model_name="gemini-3.8-flash"):
        self.model_name = model_name
        api_key = resolve_gemini_api_key()
        if api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            try:
                self.client = genai.Client()
            except Exception:
                self.client = None

        self.library = CastleLibrary()
        self.search_engine = WebSearchEngine()
        self.visual_search_engine = VisualSearchEngine()

    def _execute_deep_research(self, object_desc: str, notes: str) -> tuple[str, list]:
        _pipeline_log("[2/4] Consultando mercado y catálogos web...")
        t0 = time.perf_counter()
        clean_notes = notes.replace("FLAQUE", "PLAQUE").replace("ORG", "OR G")
        historical_queries = self.library.get_heuristic_queries(object_desc, clean_notes)
        
        if historical_queries:
            queries = historical_queries[:3]
        else:
            queries = [
                f"{object_desc} {clean_notes} auction results price hammer value",
                f"{object_desc} {clean_notes} vintage collector market price second hand",
                f"{object_desc} {clean_notes} catalog reference price guide"
            ]

        combined_results = []
        executed_queries = []
        for q in queries:
            executed_queries.append(q)
            res = self.search_engine.search_catalog(q, max_results=2)
            for item in res:
                if "cartier.com" not in item.get("href", ""):
                    combined_results.append(item)
                    
        formatted_web = self.search_engine.format_search_results_for_prompt(combined_results)
        _pipeline_log(f"[2/4] Mercado listo ({time.perf_counter() - t0:.1f}s, {len(combined_results)} resultados)")
        return formatted_web, executed_queries

    def analyze_evidence(
        self,
        object_description: str,
        context_notes: str = "",
        image_paths: list = None,
        case_id: str = "DEFAULT",
        persist_case: bool = False,
    ) -> str:
        if not self.client:
            return "[ERR_L2_GEMINI_API_KEY_MISSING]: No se ha configurado la clave de API de Gemini Pro."

        _pipeline_log("[1/4] Preparando imágenes para visión...")
        t_pipeline = time.perf_counter()
        usable_paths = [p for p in (image_paths or []) if p and os.path.exists(p)]
        _pipeline_log(f"[1/4] {len(usable_paths)} archivo(s) local(es) listos ({time.perf_counter() - t_pipeline:.1f}s)")

        clean_context = context_notes.replace("FLAQUE", "PLAQUE").replace("ORG", "OR G")
        web_context, successful_queries = self._execute_deep_research(object_description, clean_context)

        visual_context = ""
        primary_image_path = usable_paths[0] if usable_paths else None

        if primary_image_path:
            _pipeline_log("[3/4] Búsqueda visual (Google Lens / SerpApi)...")
            t_vis = time.perf_counter()
            visual_response = self.visual_search_engine.search_by_image_path(primary_image_path, max_results=4)
            visual_context = self.visual_search_engine.format_visual_results(visual_response)
            _pipeline_log(f"[3/4] Búsqueda visual finalizada ({time.perf_counter() - t_vis:.1f}s)")
        else:
            _pipeline_log("[3/4] Sin imagen local válida; se omite búsqueda visual")

        punchmarks_knowledge = get_punchmarks_context_for_prompt()

        system_instruction = (
            "Eres el Agente Pericial Senior de Investigación Forense, Autenticación, Tasación y Estrategia de Mercado de la organización CH. "
            "Tu objetivo es realizar un análisis completo que culmine en una estrategia comercial y de búsqueda de comprador (Buyer Search).\n\n"
            f"{punchmarks_knowledge}\n\n"
            "🛡️ ESCUDO ANTI-ALUCINACIÓN, AUDITORÍA MULTIVARIABLE Y GESTIÓN DE EXCEPCIONES:\n"
            "1. ANÁLISIS LITERAL DE PUNZONES Y CONTRASTES:\n"
            "   - No asumas por defecto origen europeo u occidental basándote únicamente en el estilo estético de la pieza.\n"
            "   - Inspecciona minuciosamente los caracteres grabados cruzándolos con el Diccionario Maestro de Punzones: diferencia estrictamente caracteres latinos, numeración arábiga, punzones gubernamentales (Japan Mint / kanjis / símbolos oficiales) o contrastes europeos (Estrella italiana, águila francesa, etc.).\n"
            "   - Si un punzón muestra rasgos asiáticos o símbolos no occidentales junto al título de ley (ej. 750 / K18), evalúa de manera prioritaria la orfebrería de exportación japonesa o asiática antes de forzar una atribución italiana.\n"
            "2. PETICIÓN DE EVIDENCIA VISUAL Y ORÁCULO PROACTIVO (OBLIGATORIO SI HAY DUDA):\n"
            "   - Si la certeza pericial es inferior al 95% debido a falta de visibilidad óptica en punzones o mecanismos:\n"
            "     a) Incluye la directiva exacta: `[FLAG_REQUEST_IMAGE: Descripción exacta de la macrofotografía o ángulo adicional requerido]`.\n"
            "     b) Añade obligatoriamente una subsección numerada titulada exactamente:\n"
            "        `### ❓ PREGUNTAS CLAVE PARA EL PERITO / USUARIO`\n"
            "        formulando preguntas numeradas individualmente orientadas a resolver las incertidumbres restantes.\n"
            "3. RESTRICCIÓN DE GRAMAJE Y VALORACIÓN:\n"
            "   - Si se especifica un peso real medido en balanza en las notas del perito, utilízalo como verdad absoluta para el cálculo de metales. Si no se especifica, prohíbete fijar un valor de fundición absoluto y especifica explícitamente: '[PENDIENTE DE PESAJE FÍSICO EXACTO]'.\n\n"
            "INFORMACIÓN CONFIRMADA POR EL PERITO HUMANO Y OCR:\n"
            f"- Objeto: {object_description}\n"
            f"- Inscripciones/Cuños/Dotación confirmados: {clean_context}\n\n"
            "REGLAS OBLIGATORIAS DE EVALUACIÓN, TASACIÓN Y ESTRATEGIA DE MERCADO:\n"
            "1. ⚠️ ALERTAS DE EXCEPCIÓN Y AUDITORÍA PERICIAL (Incluye aquí los Flags y las preguntas clave numeradas pendientes).\n"
            "2. 📌 IDENTIFICACIÓN FORMAL\n"
            "3. 🔬 ANÁLISIS TÉCNICO, MORFOLÓGICO Y DE MICRO-PUNZONES\n"
            "4. 📜 CATALOGACIÓN HISTÓRICA Y CONTRASTES DE ORFEBRERÍA\n"
            "5. 🌐 COINCIDENCIAS DE CATÁLOGOS WEB\n"
            "6. 🛡️ VERIFICACIÓN DE AUTENTICIDAD Y ALEACIONES\n"
            "7. ⚖️ DICTAMEN PERICIAL FINAL Y CONFIANZA (%)\n"
            "8. 💰 MÓDULO DE TASACIÓN, GRAMAJE Y BANDA DE VALORACIÓN DE MERCADO\n"
            "9. 🎯 ESTRATEGIA DE MERCADO Y BUYER SEARCH."
        )

        contents = []
        if usable_paths:
            for img_p in usable_paths:
                if img_p and os.path.exists(img_p):
                    try:
                        pil_img = Image.open(img_p)
                        contents.append(pil_img)
                    except Exception as e:
                        self.library._log_audit(f"Error cargando imagen PIL en caso {case_id}: {e}")

        prompt_text = (
            f"Objeto analizado: {object_description}\n"
            f"Inscripciones y notas confirmadas: {clean_context}\n"
            "Genera el dictamen pericial definitivo aplicando el Diccionario Maestro de Punzones, el protocolo anti-alucinación, la gestión de excepciones con preguntas guía numeradas, tasación con precios spot y Buyer Search."
        )
        contents.append(prompt_text)

        max_retries = 3
        dictamen = None

        _pipeline_log("[4/4] Llamando a IA (Gemini)...")
        t_ia = time.perf_counter()
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.1
                    )
                )
                dictamen = response.text
                break
            except Exception as e:
                self.library._log_audit(f"Intento {attempt+1} fallido de inferencia Gemini: {e}")
                if attempt < max_retries - 1:
                    time.sleep(3 * (attempt + 1))
                else:
                    return f"[ERR_L3_GEMINI_INFERENCE_FAILED]: {str(e)}"

        _pipeline_log(f"[4/4] Dictamen generado ({time.perf_counter() - t_ia:.1f}s)")
        _pipeline_log(f"Pipeline completo ({time.perf_counter() - t_pipeline:.1f}s total)")

        if persist_case:
            self.library.save_case(
                case_id=case_id,
                object_description=object_description,
                context_notes=clean_context,
                dictamen=dictamen,
                image_paths=usable_paths,
                successful_queries=successful_queries,
            )

        return dictamen

    def update_appraisal(self, case_folder: str, object_desc: str, notes: str) -> str:
        if not self.client:
            return "[ERR]: API Key no disponible."
        
        md_path = os.path.join(case_folder, "dictamen.md")
        existing_text = ""
        if os.path.exists(md_path):
            with open(md_path, "r", encoding="utf-8") as f:
                existing_text = f.read()

        prompt = (
            f"Basándote en el expediente existente para el objeto '{object_desc}' con notas '{notes}', "
            "actualiza o recalcula el 'MÓDULO DE TASACIÓN, GRAMAJE Y BANDA DE VALORACIÓN DE MERCADO' aplicando los precios de metales en tiempo real y refuerza la 'ESTRATEGIA DE BUYER SEARCH'."
        )
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt, existing_text],
                config=types.GenerateContentConfig(temperature=0.2)
            )
            updated_dictamen = existing_text + "\n\n---\n\n### 🔄 REEVALUACIÓN DINÁMICA DE TASACIÓN Y OJO EXPERTO\n" + response.text
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(updated_dictamen)
            return updated_dictamen
        except Exception as e:
            return f"Error al actualizar la tasación: {e}"

LocalHermesExplorer = LocalAIAgent