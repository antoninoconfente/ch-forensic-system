import os
import sys
import json
import re
import requests
import streamlit as st
from PIL import Image

# ---------------------------------------------------------
# BLINDAJE ABSOLUTO DE RUTAS DE IMPORTACIÓN (PATH RESOLUTION)
# ---------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from src.research.ai_agent import LocalAIAgent, CastleLibrary, sanitize_context_notes
from src.research.market_engine import MarketEngine

# ==========================================
# CONFIGURACIÓN DE PÁGINA Y ESTÉTICA EDITORIAL
# ==========================================
st.set_page_config(
    page_title="CH — Peritaje Forense de Lujo",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Inyección de Estilos CSS Editorial de Lujo y Bloque de Auditoría Visible
st.markdown("""
    <style>
    .stApp {
        background-color: #f7f5f0 !important;
        color: #1a1a1a !important;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }
    h1, h2, h3, h4 {
        font-family: 'Georgia', Cambria, serif !important;
        color: #1a1a1a !important;
        font-weight: 400 !important;
        letter-spacing: -0.5px !important;
    }
    .stButton>button {
        background-color: transparent !important;
        color: #1a1a1a !important;
        font-weight: 400 !important;
        font-size: 0.8rem !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0px !important;
        text-decoration: underline !important;
        text-transform: none !important;
        letter-spacing: 0.5px !important;
        text-align: left !important;
    }
    .stButton>button:hover {
        background-color: transparent !important;
        color: #b89753 !important;
    }
    [data-testid="stFileUploader"] {
        background-color: #eae6db !important;
        border: 1px solid #d5d0c1 !important;
        border-radius: 2px !important;
        padding: 10px !important;
    }
    [data-testid="stFileUploader"] section {
        background-color: #f2efe9 !important;
        border: none !important;
    }
    .editorial-card {
        background-color: transparent !important;
        border: none !important;
        padding: 10px 5px 20px 5px !important;
        margin-bottom: 20px;
    }
    .editorial-container {
        background-color: #faf8f3 !important;
        border: 1px solid #e6e2cc !important;
        border-radius: 2px !important;
        padding: 25px !important;
        margin-bottom: 20px;
    }
    .audit-box {
        background-color: #fdf6e2 !important;
        border: 1px solid #e6d29c !important;
        border-left: 4px solid #b89753 !important;
        padding: 20px !important;
        border-radius: 2px !important;
        margin-bottom: 20px;
    }
    .question-card {
        background-color: #f4efe6 !important;
        border: 1px solid #e3dec3 !important;
        padding: 15px !important;
        border-radius: 2px !important;
        margin-bottom: 15px;
    }
    .stImage {
        width: 100% !important;
        display: flex;
        justify-content: center;
        align-items: center;
        overflow: hidden;
        border-radius: 2px;
        background-color: #eae6db;
        margin-bottom: 8px;
    }
    .stImage img {
        width: 100% !important;
        height: 210px !important;
        object-fit: cover !important;
        border-radius: 1px !important;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# Inicializar Agente, Librería y Motor de Mercado Dinámico
agent = LocalAIAgent()
library = CastleLibrary()
market_engine = MarketEngine()

# ==========================================
# GESTIÓN DE ESTADO DE NAVEGACIÓN (STATE MACHINE)
# ==========================================
if "current_view" not in st.session_state:
    st.session_state.current_view = "main"
if "last_dictamen" not in st.session_state:
    st.session_state.last_dictamen = ""
if "active_case_id" not in st.session_state:
    st.session_state.active_case_id = ""
if "selected_case_id" not in st.session_state:
    st.session_state.selected_case_id = None
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# Función auxiliar para separar el bloque de alertas y el dictamen comercial
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


def _flatten_answer_summary(answer_text: str, max_len: int = 110) -> str:
    flat = sanitize_context_notes(answer_text)
    if not flat:
        return ""
    if flat.lower() in {"pendiente", "n/a", "na", "si", "sí", "no", "-", "."}:
        return flat.capitalize() if len(flat) > 1 else flat
    first = re.split(r"(?<=[.!?])\s+", flat)[0].strip()
    if len(first) > max_len:
        first = first[: max_len - 1].rsplit(" ", 1)[0] + "…"
    return first


def build_flat_context_notes(existing_notes: str, answer_summaries: list) -> str:
    base = sanitize_context_notes(existing_notes)
    shorts = [_flatten_answer_summary(item) for item in answer_summaries]
    shorts = [item for item in shorts if item]
    if base and shorts:
        return f"{base}. {'; '.join(shorts)}"
    if shorts:
        return "; ".join(shorts)
    return base or "Sin notas adicionales"

# Función auxiliar para descarga de URLs / Google Drive
def download_image_from_url(url, save_dir="data/temp"):
    os.makedirs(save_dir, exist_ok=True)
    try:
        session = requests.Session()
        if "drive.google.com" in url:
            if "/file/d/" in url:
                file_id = url.split("/file/d/")[1].split("/")[0]
            elif "id=" in url:
                file_id = url.split("id=")[1].split("&")[0]
            else:
                return None
            URL = "https://docs.google.com/uc?export=download"
            response = session.get(URL, params={'id': file_id}, stream=True, timeout=10)
        else:
            response = session.get(url, stream=True, timeout=10)

        if response.status_code == 200:
            filename = f"cloud_img_{os.urandom(2).hex()}.jpg"
            file_path = os.path.join(save_dir, filename)
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=32768):
                    if chunk:
                        f.write(chunk)
            try:
                with Image.open(file_path) as img:
                    img.verify()
                return file_path
            except Exception:
                if os.path.exists(file_path):
                    os.remove(file_path)
                return None
    except Exception:
        pass
    return None

# ==========================================
# VISTA 1: MAIN PANEL (TWO-COLUMN LAYOUT)
# ==========================================
if st.session_state.current_view == "main":
    
    st.markdown("<h1 style='text-align: center; color: #1a1a1a; margin-top: 1rem; font-size: 2.2rem;'>DIVISIÓN DE PERITAJE Y AUTENTICACIÓN FORENSE</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #666666; font-size: 0.95rem; margin-bottom: 2rem; letter-spacing: 0.5px;'>Sistema autónomo de investigación documental y material para alta relojería y objetos de valor</p>", unsafe_allow_html=True)
    st.markdown("<hr style='border: none; border-top: 1px solid #e3dec3; margin-bottom: 2.5rem;'>", unsafe_allow_html=True)

    col_left, col_right = st.columns([1, 1.3], gap="large")

    with col_left:
        st.markdown("### Archivo Histórico")
        st.markdown("<p style='color: #666; font-size: 0.9rem;'>Acceso directo al registro general de peritajes realizados.</p>", unsafe_allow_html=True)
        
        if st.button("Ver Archivo Completo de Casos", use_container_width=True):
            st.session_state.current_view = "library"
            st.rerun()
            
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### Últimos Expedientes Registrados")
        
        all_cases = library.get_all_cases()
        recent_cases = all_cases[-3:][::-1]
        
        if not recent_cases:
            st.markdown("<p style='color: #888; font-style: italic; font-size: 0.9rem;'>No hay peritajes registrados en el sistema.</p>", unsafe_allow_html=True)
        else:
            for item in recent_cases:
                c_id = item.get("case_id")
                clean_name = item.get("context_notes") if (item.get("context_notes") and item.get("context_notes") != "Sin notas adicionales") else item.get("object_description", "Objeto peritado")
                if "analizada por visión" in clean_name:
                    clean_name = "Pieza de Alta Gama"
                img_p = item.get("image_path")
                
                with st.container():
                    st.markdown("<div class='editorial-card'>", unsafe_allow_html=True)
                    sub_c1, sub_c2 = st.columns([1, 1.5])
                    with sub_c1:
                        if img_p and os.path.exists(img_p):
                            st.image(img_p, use_container_width=True)
                        else:
                            st.markdown("<span style='font-size:0.8rem; color:#888;'>Sin miniatura</span>", unsafe_allow_html=True)
                    with sub_c2:
                        st.markdown(f"**{clean_name}**")
                        st.markdown(f"<p style='font-size: 0.75rem; color: #888; margin-bottom: 6px;'>Ref: {c_id}</p>", unsafe_allow_html=True)
                        if st.button("Ver Ficha", key=f"btn_quick_{c_id}", use_container_width=True):
                            st.session_state.selected_case_id = c_id
                            st.session_state.current_view = "detail"
                            st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

    with col_right:
        st.markdown("### Nuevo Peritaje Activo")
        st.markdown("<p style='color: #666; font-size: 0.9rem;'>Cargue las tomas fotográficas o proporcione enlaces para iniciar la investigación, tasación y Buyer Search.</p>", unsafe_allow_html=True)
        
        spot_info = market_engine.get_metal_spot_prices()
        st.markdown(f"<p style='font-size: 0.8rem; color: #889753; background-color: #f2efe9; padding: 6px 10px; border-radius: 2px; border-left: 3px solid #b89753;'>⚡ Grounding Activo — Spot Oro: {spot_info.get('GOLD_EUR_PER_GRAM')} €/g | Plata: {spot_info.get('SILVER_EUR_PER_GRAM')} €/g</p>", unsafe_allow_html=True)

        source_mode = st.radio("Fuente de Ingesta", ["Archivos Locales", "URL / Google Drive"], horizontal=True, label_visibility="collapsed")
        
        image_paths = []
        if source_mode == "Archivos Locales":
            current_uploader_key = f"uploader_{st.session_state.uploader_key}"
            uploaded_files = st.file_uploader(
                "Seleccionar evidencias fotográficas (JPG, PNG)",
                type=["jpg", "jpeg", "png"],
                accept_multiple_files=True,
                key=current_uploader_key
            )
            if uploaded_files:
                os.makedirs("data/temp", exist_ok=True)
                cols_preview = st.columns(min(len(uploaded_files), 3))
                for idx, uf in enumerate(uploaded_files):
                    tmp_p = os.path.join("data/temp", uf.name)
                    with open(tmp_p, "wb") as f:
                        f.write(uf.getbuffer())
                    image_paths.append(tmp_p)
                    with cols_preview[idx % len(cols_preview)]:
                        st.image(uf, caption=f"Evidencia {idx+1}", use_container_width=True)
        else:
            urls_text = st.text_area("Enlaces de imágenes (uno por línea)", placeholder="https://... o enlace compartido de Google Drive")
            if urls_text:
                url_list = [u.strip() for u in urls_text.split("\n") if u.strip()]
                cols_preview = st.columns(min(len(url_list), 3))
                for idx, u in enumerate(url_list):
                    dl_path = download_image_from_url(u)
                    if dl_path:
                        image_paths.append(dl_path)
                        with cols_preview[idx % len(cols_preview)]:
                            st.image(dl_path, caption=f"Evidencia Nube {idx+1}", use_container_width=True)
                    else:
                        st.warning(f"No se pudo procesar el enlace: {u}")

        st.markdown("<br>", unsafe_allow_html=True)
        extra_notes = st.text_input("Notas de Referencia o Cuños Visibles (Incluir caja/dotación si aplica)", placeholder="Ej. Con caja original, número de serie...")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Ejecutar Investigación, Tasación y Buyer Search", use_container_width=True):
            if not image_paths:
                st.warning("Por favor, aporte al menos una evidencia fotográfica válida.")
            else:
                case_id = f"EXP-CH-{os.urandom(2).hex().upper()}"
                obj_desc = extra_notes if extra_notes else "Pieza de alta gama analizada por visión artificial"
                
                market_context_notes = f"{extra_notes} [SPOT MARKET DATA - Gold: {spot_info.get('GOLD_EUR_PER_GRAM')}€/g, Silver: {spot_info.get('SILVER_EUR_PER_GRAM')}€/g]"
                
                with st.spinner("Consultando metales en tiempo real y conectando con motores de análisis..."):
                    dictamen_text = agent.analyze_evidence(
                        object_description=obj_desc,
                        context_notes=market_context_notes,
                        image_paths=image_paths,
                        case_id=case_id
                    )
                    st.session_state.last_dictamen = dictamen_text
                    st.session_state.active_case_id = case_id
                    st.session_state.current_view = "result"
                    st.rerun()

# ==========================================
# VISTA 2: RESULT SCREEN (ESTADO PERSISTENTE INTELIGENTE SUBFASE 3.3)
# ==========================================
elif st.session_state.current_view == "result":
    
    st.markdown("<h2 style='text-align: center; margin-top: 1rem;'>Dictamen Pericial, Tasación y Buyer Search Generados</h2>", unsafe_allow_html=True)
    st.markdown("<hr style='border: none; border-top: 1px solid #e3dec3; margin-bottom: 2rem;'>", unsafe_allow_html=True)

    raw_dictamen = st.session_state.get("last_dictamen", "")
    alerts_section, commercial_section = parse_dictamen_sections(raw_dictamen)

    active_case = st.session_state.get("active_case_id")
    case_folder = os.path.join("data", "cases", active_case) if active_case else ""
    meta_path = os.path.join(case_folder, "metadata.json") if case_folder else ""
    
    case_metadata = {}
    if meta_path and os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as mf:
            case_metadata = json.load(mf)
    
    resolved_questions_store = case_metadata.get("resolved_questions", [])

    if alerts_section:
        visible_alert_lines = []
        for alert_line in alerts_section.split("\n"):
            stripped_line = alert_line.strip()
            if stripped_line and (
                _question_is_resolved(stripped_line, resolved_questions_store)
                or _question_is_resolved(re.sub(r"^(\d+[\.\)\:]|[-*•])\s+", "", stripped_line), resolved_questions_store)
            ):
                continue
            visible_alert_lines.append(alert_line)
        visible_alerts = "\n".join(visible_alert_lines).strip() or "Sin incertidumbres pendientes de resolución."
        st.markdown(f"""
            <div class='audit-box'>
                <h4 style='color: #8c6d28; margin-top: 0; font-size: 1.1rem;'>🛡️ Panel de Auditoría e Incertidumbres del Agente</h4>
                <div style='color: #333; font-size: 0.95rem;'>{visible_alerts}</div>
            </div>
        """, unsafe_allow_html=True)
        
        extracted_questions = extract_questions_from_alerts(
            alerts_section, resolved_questions=resolved_questions_store
        )
        pending_questions = extracted_questions

        if pending_questions:
            with st.expander(f"💬 Interrogatorio Activo: {len(pending_questions)} Incertidumbre(s) Pendiente(s) de Resolución", expanded=True):
                st.markdown("<p style='font-size: 0.95rem; color: #b89753; font-weight: 500;'>Responde solo a las cuestiones que deseas aclarar ahora. Las que dejes vacías o sin responder se mantendrán en suspenso para el futuro:</p>", unsafe_allow_html=True)
                
                user_answers = {}
                user_urls = {}
                user_files_dict = {}

                for q_idx, q_text in enumerate(pending_questions):
                    st.markdown(f"<div class='question-card'>", unsafe_allow_html=True)
                    st.markdown(f"**Cuestión Pendiente {q_idx+1}:** {q_text}")
                    
                    qc1, qc2 = st.columns([1.2, 1], gap="medium")
                    with qc1:
                        ans = st.text_input(f"Respuesta / Aclaración", placeholder="Escribe tu apreciación o 'Pendiente'...", key=f"q_ans_{active_case}_{q_idx}")
                        url_val = st.text_input(f"URL de referencia opcional", placeholder="https://...", key=f"q_url_{active_case}_{q_idx}")
                        user_answers[q_idx] = ans
                        user_urls[q_idx] = url_val
                    with qc2:
                        f_uploaded = st.file_uploader(f"Foto/Evidencia complementaria", type=["jpg", "jpeg", "png"], key=f"q_file_{active_case}_{q_idx}")
                        user_files_dict[q_idx] = f_uploaded
                    st.markdown(f"</div>", unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("⚡ Procesar Respuestas, Consolidar y Recalcular", use_container_width=True):
                    with st.spinner("Asimilando respuestas, archivando cuestiones resueltas y recalculando expediente..."):
                        evidence_folder = os.path.join(case_folder, "evidence")
                        os.makedirs(evidence_folder, exist_ok=True)
                        
                        answer_summaries = []
                        newly_resolved = []

                        for q_idx, q_text in enumerate(pending_questions):
                            ans = user_answers.get(q_idx, "").strip()
                            url_v = user_urls.get(q_idx, "").strip()
                            f_up = user_files_dict.get(q_idx)
                            
                            if ans or f_up is not None or url_v:
                                answer_text = ans if ans else "Evidencia/URL aportada"
                                answer_summaries.append(f"Aclaración: {answer_text}")
                                newly_resolved.append(q_text)
                            
                            if f_up is not None:
                                ext = os.path.splitext(f_up.name)[1]
                                new_filename = f"evidence_q{q_idx+1}_{os.urandom(2).hex()}{ext}"
                                new_file_path = os.path.join(evidence_folder, new_filename)
                                with open(new_file_path, "wb") as f:
                                    f.write(f_up.getbuffer())

                        updated_resolved_store = list(dict.fromkeys(resolved_questions_store + newly_resolved))
                        final_clean_notes = build_flat_context_notes(
                            case_metadata.get("context_notes", ""),
                            answer_summaries,
                        )

                        if meta_path and os.path.exists(meta_path):
                            with open(meta_path, "r", encoding="utf-8") as mf:
                                mdata = json.load(mf)
                            mdata["resolved_questions"] = updated_resolved_store
                            mdata["context_notes"] = final_clean_notes
                            with open(meta_path, "w", encoding="utf-8") as mf:
                                json.dump(mdata, mf, indent=2, ensure_ascii=False)

                        all_ev_images = [os.path.join(evidence_folder, f) for f in sorted(os.listdir(evidence_folder)) if f.lower().endswith(('png', 'jpg', 'jpeg'))]
                        orig_desc = case_metadata.get("object_description", "Pieza peritada")

                        updated_dictamen = agent.analyze_evidence(
                            object_description=orig_desc,
                            context_notes=final_clean_notes,
                            image_paths=all_ev_images,
                            case_id=active_case
                        )
                        st.session_state.last_dictamen = updated_dictamen
                        st.success("¡Cuestiones consolidadas, expediente actualizado y preguntas resueltas archivadas con éxito!")
                        st.rerun()
        else:
            st.markdown("<p style='color: #2e7d32; font-weight: 500; font-size: 0.95rem; background-color: #e8f5e9; padding: 12px; border-radius: 2px;'>✨ Todas las incertidumbres detectadas en este expediente han sido respondidas y consolidadas satisfactoriamente.</p>", unsafe_allow_html=True)

    col_split_left, col_split_right = st.columns([1, 1.2], gap="large")

    with col_split_left:
        st.markdown("### Evidencias Aportadas")
        case_ev_folder = os.path.join(case_folder, "evidence") if case_folder else ""
        if case_ev_folder and os.path.exists(case_ev_folder):
            ev_files = sorted(os.listdir(case_ev_folder))
            for f in ev_files:
                f_path = os.path.join(case_ev_folder, f)
                st.image(f_path, caption=f"Registro Fotográfico — {f}", use_container_width=True)
        else:
            st.info("Imágenes temporales procesadas.")

    with col_split_right:
        st.markdown("### Informe Técnico, Económico y Comercial")
        st.markdown("<div class='editorial-container'>", unsafe_allow_html=True)
        st.markdown(commercial_section)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br><hr style='border: none; border-top: 1px solid #e3dec3; margin: 2rem 0;'>", unsafe_allow_html=True)

    b_col1, b_col2, b_col3 = st.columns([1, 1, 1])
    with b_col1:
        if st.button("Volver al Panel Principal", use_container_width=True):
            st.session_state.current_view = "main"
            st.session_state.uploader_key += 1
            st.rerun()
    with b_col2:
        if st.button("Guardar en Archivo General", use_container_width=True):
            st.success("Expediente consolidado y guardado correctamente en la Castle Library.")
    with b_col3:
        if st.button("Descartar Expediente", use_container_width=True):
            library.delete_case(active_case)
            st.session_state.current_view = "main"
            st.session_state.uploader_key += 1
            st.rerun()

# ==========================================
# VISTA 3: LIBRARY (GRID DE 3 COLUMNAS)
# ==========================================
elif st.session_state.current_view == "library":
    
    st.markdown("<h2 style='text-align: center; margin-top: 1rem;'>Archivo General de Casos — Castle Library</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #666;'>Galería documental de piezas autenticadas, tasadas y estrategias de mercado</p>", unsafe_allow_html=True)
    st.markdown("<hr style='border: none; border-top: 1px solid #e3dec3; margin-bottom: 2.5rem;'>", unsafe_allow_html=True)

    cases = library.get_all_cases()

    if not cases:
        st.markdown("<p style='text-align: center; color: #888;'>No existen casos registrados en el sistema.</p>", unsafe_allow_html=True)
    else:
        grid_cols = 3
        rows = [cases[i:i + grid_cols] for i in range(0, len(cases), grid_cols)]

        for row in rows:
            cols = st.columns(grid_cols)
            for idx, item in enumerate(row):
                with cols[idx]:
                    st.markdown("<div class='editorial-card'>", unsafe_allow_html=True)
                    
                    clean_name = item.get("context_notes") if (item.get("context_notes") and item.get("context_notes") != "Sin notas adicionales") else item.get("object_description", "Objeto peritado")
                    if "analizada por visión" in clean_name:
                        clean_name = "Pieza de Alta Gama"
                    
                    st.markdown(f"**{clean_name}**")
                    st.markdown(f"<p style='font-size: 0.75rem; color: #888; margin-bottom: 8px;'>Ref: {item.get('case_id')}</p>", unsafe_allow_html=True)
                    
                    img_path = item.get("image_path")
                    if img_path and os.path.exists(img_path):
                        st.image(img_path, use_container_width=True)
                    else:
                        st.markdown("<p style='color: #888; font-size: 0.8rem;'>Sin imagen disponible</p>", unsafe_allow_html=True)
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    lnk_col1, lnk_col2 = st.columns(2)
                    with lnk_col1:
                        if st.button("Ver Ficha", key=f"lib_view_{item.get('case_id')}_{idx}", use_container_width=True):
                            st.session_state.selected_case_id = item.get("case_id")
                            st.session_state.current_view = "detail"
                            st.rerun()
                    with lnk_col2:
                        if st.button("Eliminar", key=f"lib_del_{item.get('case_id')}_{idx}", use_container_width=True):
                            library.delete_case(item.get("case_id"))
                            st.rerun()
                            
                    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br><hr style='border: none; border-top: 1px solid #e3dec3; margin: 2rem 0;'>", unsafe_allow_html=True)
    
    col_ret1, col_ret2, col_ret3 = st.columns([1, 1, 1])
    with col_ret2:
        if st.button("Volver al Panel Principal", use_container_width=True):
            st.session_state.current_view = "main"
            st.rerun()

# ==========================================
# VISTA 4: DETAIL VIEW
# ==========================================
elif st.session_state.current_view == "detail":
    
    target_id = st.session_state.get("selected_case_id")
    all_cases = library.get_all_cases()
    case_item = next((c for c in all_cases if c.get("case_id") == target_id), None)
    
    if not case_item and all_cases:
        case_item = all_cases[-1]

    if not case_item:
        st.warning("No se ha seleccionado ningún expediente válido.")
        if st.button("Volver al Panel Principal"):
            st.session_state.current_view = "main"
            st.rerun()
    else:
        clean_title = case_item.get("context_notes") if (case_item.get("context_notes") and case_item.get("context_notes") != "Sin notas adicionales") else case_item.get("object_description", "Ficha Técnica")
        if "analizada por visión" in clean_title:
            clean_title = "Ficha Técnica, Tasación y Buyer Search"
        
        st.markdown(f"<h2 style='text-align: center; margin-top: 1rem;'>{clean_title}</h2>", unsafe_allow_html=True)
        st.markdown(f"<p style='text-align: center; color: #666;'>Expediente de Referencia: {case_item.get('case_id')}</p>", unsafe_allow_html=True)
        st.markdown("<hr style='border: none; border-top: 1px solid #e3dec3; margin-bottom: 2rem;'>", unsafe_allow_html=True)

        det_col1, det_col2 = st.columns([1, 1.3], gap="large")
        folder_path = case_item.get("folder_path")

        with det_col1:
            st.markdown("### Evidencias Fotográficas")
            if folder_path and os.path.exists(folder_path):
                ev_folder = os.path.join(folder_path, "evidence")
                if os.path.exists(ev_folder):
                    for img_file in sorted(os.listdir(ev_folder)):
                        full_p = os.path.join(folder_path, "evidence", img_file)
                        st.image(full_p, caption=f"Evidencia Documental — {img_file}", use_container_width=True)
            else:
                img_p = case_item.get("image_path")
                if img_p and os.path.exists(img_p):
                    st.image(img_p, use_container_width=True)

        with det_col2:
            st.markdown("### Dictamen, Tasación y Estrategia Comercial")
            
            if st.button("Actualizar Tasación y Generar Buyer Search", key=f"btn_appraise_detail_{case_item.get('case_id')}", use_container_width=True):
                with st.spinner("Consultando tendencias de mercado y generando perfilado de compradores..."):
                    updated_dictamen = agent.update_appraisal(
                        case_folder=folder_path,
                        object_desc=case_item.get('object_description', ''),
                        notes=case_item.get('context_notes', '')
                    )
                    st.success("¡Tasación y estrategia de mercado actualizadas con éxito!")
                    st.rerun()

            dictamen_text = "No se ha encontrado el contenido del dictamen."
            if folder_path:
                md_file = os.path.join(folder_path, "dictamen.md")
                if os.path.exists(md_file):
                    with open(md_file, "r", encoding="utf-8") as f:
                        dictamen_text = f.read()
            
            det_alerts, det_commercial = parse_dictamen_sections(dictamen_text)

            if det_alerts:
                st.markdown(f"""
                    <div class='audit-box'>
                        <h4 style='color: #8c6d28; margin-top: 0; font-size: 1.1rem;'>🛡️ Panel de Auditoría e Incertidumbres (Modo Trabajo Activo)</h4>
                        <div style='color: #333; font-size: 0.95rem;'>{det_alerts}</div>
                    </div>
                """, unsafe_allow_html=True)

            st.markdown("<div class='editorial-container'>", unsafe_allow_html=True)
            st.markdown(det_commercial)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<br><hr style='border: none; border-top: 1px solid #e3dec3; margin: 2rem 0;'>", unsafe_allow_html=True)

        back_c1, back_c2, back_c3 = st.columns([1, 1, 1])
        with back_c1:
            if st.button("Volver al Archivo General", use_container_width=True):
                st.session_state.current_view = "library"
                st.rerun()
        with back_c3:
            if st.button("Volver al Panel Principal", use_container_width=True):
                st.session_state.current_view = "main"
                st.rerun()