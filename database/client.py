"""Cliente Supabase y repositorio SQLAlchemy. No arranca la interfaz."""

import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import selectinload, sessionmaker
from supabase import create_client

from agents.schemas import infer_parent_domain, normalize_snake_key
from database.models import (
    Base,
    Case,
    CaseEmbedding,
    Client,
    DomainRubric,
    Evidence,
    GemologyData,
    Lot,
    UserProfile,
    VALID_USER_ROLES,
)

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SUPABASE_SECRET_KEY = os.environ.get("SUPABASE_SECRET_KEY") or SUPABASE_KEY
DATABASE_URL = os.environ.get("DATABASE_URL")
# Bucket privado (public: False en Supabase). Acceso vía URLs firmadas únicamente.
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "evidence")


def _psycopg2_url(url: str | None) -> str | None:
    if not url:
        return url
    if url.startswith("postgresql+psycopg2://") or url.startswith("postgres+psycopg2://"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + url[len("postgresql://"):]
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://"):]
    return url


supabase = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)
engine = create_engine(
    _psycopg2_url(DATABASE_URL),
    pool_pre_ping=True,
    pool_recycle=300,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

_CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def init_db() -> None:
    """Crea client y lot. En una base ya existente añade lot_id y pasa raw_json a JSONB."""
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS lot_id VARCHAR"))
        connection.execute(text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'cases_lot_id_fkey'
                ) THEN
                    ALTER TABLE cases
                    ADD CONSTRAINT cases_lot_id_fkey
                    FOREIGN KEY (lot_id) REFERENCES lot(id) ON DELETE SET NULL;
                END IF;
            END $$;
            """
        ))
        connection.execute(text(
            """
            ALTER TABLE gemology_data
            ALTER COLUMN raw_json TYPE JSONB
            USING raw_json::jsonb
            """
        ))
        connection.execute(text(
            "ALTER TABLE domain_rubrics ADD COLUMN IF NOT EXISTS parent_domain VARCHAR"
        ))
        connection.execute(text(
            """
            CREATE INDEX IF NOT EXISTS ix_domain_rubrics_parent_domain
            ON domain_rubrics (parent_domain)
            """
        ))
        connection.execute(text(
            """
            UPDATE domain_rubrics
            SET parent_domain = UPPER(split_part(replace(taxonomy_key, '-', '_'), '_', 1))
            WHERE parent_domain IS NULL OR parent_domain = ''
            """
        ))


def _session():
    return SessionLocal()


def _resolve_default_role(email: str) -> str:
    import os
    from sqlalchemy import func

    admin_email = (os.getenv("ADMIN_EMAIL") or "").strip().casefold()
    if admin_email and (email or "").strip().casefold() == admin_email:
        return "admin"
    with SessionLocal() as session:
        count = session.scalar(select(func.count()).select_from(UserProfile)) or 0
        if count == 0:
            return "admin"
    return "analyst"


def _profile_to_dict(profile: UserProfile) -> dict:
    return {
        "user_id": profile.user_id,
        "email": profile.email,
        "role": profile.role,
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
    }


def get_or_create_user_profile(user_id: str, email: str) -> dict:
    """Perfil de acceso por rol. Primer usuario u ADMIN_EMAIL → admin; resto → analyst por defecto."""
    from datetime import datetime, timezone

    uid = (user_id or "").strip()
    mail = (email or "").strip()
    if not uid or not mail:
        raise ValueError("user_id y email son obligatorios para el perfil.")

    with SessionLocal() as session:
        profile = session.get(UserProfile, uid)
        if profile is None:
            profile = session.scalar(select(UserProfile).where(UserProfile.email == mail))
        if profile is None:
            role = _resolve_default_role(mail)
            profile = UserProfile(
                user_id=uid,
                email=mail,
                role=role if role in VALID_USER_ROLES else "analyst",
                created_at=datetime.now(timezone.utc),
            )
            session.add(profile)
            session.commit()
            session.refresh(profile)
        elif profile.email != mail:
            profile.email = mail
            session.commit()
            session.refresh(profile)
        session.expunge(profile)
        return _profile_to_dict(profile)


def update_user_role(user_id: str, new_role: str) -> dict:
    role = (new_role or "").strip().lower()
    if role not in VALID_USER_ROLES:
        raise ValueError(f"Rol inválido: {new_role}. Use admin, analyst o viewer.")
    with SessionLocal() as session:
        profile = session.get(UserProfile, user_id)
        if profile is None:
            raise ValueError("Perfil de usuario no encontrado.")
        profile.role = role
        session.commit()
        session.refresh(profile)
        session.expunge(profile)
        return _profile_to_dict(profile)


def _merge_unique_strings(existing: list | None, incoming: list | None) -> list:
    seen: set[str] = set()
    merged: list[str] = []
    for item in list(existing or []) + list(incoming or []):
        text = str(item or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        merged.append(text)
    return merged


def _merge_cad_guides(existing: str | None, incoming: str | None) -> str:
    base = (existing or "").strip()
    extra = (incoming or "").strip()
    if not extra:
        return base
    if not base:
        return extra
    if extra.casefold() in base.casefold():
        return base
    return f"{base}\n\n—\n\n{extra}"


def _match_rubric_row(session, taxonomy_key: str) -> DomainRubric | None:
    canonical = normalize_snake_key(taxonomy_key)
    if not canonical:
        return None
    rubric = session.get(DomainRubric, canonical)
    if rubric is not None:
        return rubric
    for row in session.scalars(select(DomainRubric)):
        if normalize_snake_key(row.taxonomy_key) == canonical:
            return row
    return None


def list_existing_rubrics_summary() -> list[dict]:
    """Catálogo compacto para triaje taxonómico (reutilizar antes de crear)."""
    with SessionLocal() as session:
        rows = list(session.scalars(select(DomainRubric).order_by(DomainRubric.parent_domain, DomainRubric.taxonomy_key)))
        summary = []
        for row in rows:
            parent = normalize_snake_key(row.parent_domain or infer_parent_domain(row.taxonomy_key))
            summary.append(
                {
                    "taxonomy_key": normalize_snake_key(row.taxonomy_key),
                    "parent_domain": parent,
                    "display_name": row.display_name,
                    "version": int(row.version or 1),
                }
            )
        session.expunge_all()
        return summary


def list_rubrics_by_parent_domain(parent_domain: str) -> list[DomainRubric]:
    parent = normalize_snake_key(parent_domain)
    if not parent:
        return []
    with SessionLocal() as session:
        rows = list(
            session.scalars(
                select(DomainRubric)
                .where(DomainRubric.parent_domain == parent)
                .order_by(DomainRubric.taxonomy_key)
            )
        )
        if not rows:
            rows = [
                row
                for row in session.scalars(select(DomainRubric))
                if normalize_snake_key(row.parent_domain or infer_parent_domain(row.taxonomy_key)) == parent
            ]
        session.expunge_all()
        return rows


def get_domain_rubric(taxonomy_key: str) -> DomainRubric | None:
    if not (taxonomy_key or "").strip():
        return None
    with SessionLocal() as session:
        rubric = _match_rubric_row(session, taxonomy_key)
        if rubric is not None:
            session.expunge(rubric)
        return rubric


def upsert_domain_rubric(rubric_data: dict) -> DomainRubric:
    """Crea o versiona una rúbrica forense, fusionando criterios nuevos aprendidos."""
    from datetime import datetime, timezone

    payload = dict(rubric_data or {})
    key = normalize_snake_key(payload.get("taxonomy_key") or "")
    if not key:
        raise ValueError("taxonomy_key es obligatorio para upsert_domain_rubric")
    parent = normalize_snake_key(payload.get("parent_domain") or infer_parent_domain(key))

    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        existing = _match_rubric_row(session, key)
        if existing is None:
            rubric = DomainRubric(
                taxonomy_key=key,
                parent_domain=parent,
                display_name=str(payload.get("display_name") or key),
                version=1,
                inspection_checklist=list(payload.get("inspection_checklist") or []),
                authenticity_red_flags=list(payload.get("authenticity_red_flags") or []),
                cad_measurement_guide=str(payload.get("cad_measurement_guide") or ""),
                updated_at=now,
            )
            session.add(rubric)
            session.commit()
            session.refresh(rubric)
            session.expunge(rubric)
            return rubric

        if not existing.parent_domain:
            existing.parent_domain = parent
        elif payload.get("parent_domain"):
            existing.parent_domain = parent
        existing.version = int(existing.version or 1) + 1
        if payload.get("display_name"):
            existing.display_name = str(payload["display_name"])
        existing.inspection_checklist = _merge_unique_strings(
            existing.inspection_checklist,
            payload.get("inspection_checklist"),
        )
        existing.authenticity_red_flags = _merge_unique_strings(
            existing.authenticity_red_flags,
            payload.get("authenticity_red_flags"),
        )
        existing.cad_measurement_guide = _merge_cad_guides(
            existing.cad_measurement_guide,
            payload.get("cad_measurement_guide"),
        )
        existing.updated_at = now
        session.commit()
        session.refresh(existing)
        session.expunge(existing)
        return existing


def save_case(case: Case) -> Case:
    """Inserta o actualiza el expediente y sustituye gemología y evidencias vinculadas."""
    session = _session()
    try:
        existing = session.scalar(
            select(Case)
            .options(selectinload(Case.gemology_records), selectinload(Case.evidences))
            .where(Case.id == case.id)
        )
        if existing is None:
            session.add(case)
        else:
            for name in (
                "status",
                "custom_brand",
                "custom_title",
                "object_description",
                "intake_notes",
                "context_notes",
                "dictamen_text",
            ):
                setattr(existing, name, getattr(case, name))
            existing.gemology_records.clear()
            existing.evidences.clear()
            session.flush()
            for record in list(case.gemology_records or []):
                existing.gemology_records.append(GemologyData(
                    case_id=case.id,
                    applies=bool(record.applies),
                    subject=record.subject,
                    metal_kind=record.metal_kind,
                    metal_grams=record.metal_grams,
                    total_carats=record.total_carats,
                    valuation_eur=record.valuation_eur,
                    raw_json=record.raw_json,
                ))
            for record in list(case.evidences or []):
                existing.evidences.append(Evidence(
                    case_id=case.id,
                    storage_path=record.storage_path,
                    is_main=bool(record.is_main),
                ))
        session.commit()
        loaded = session.scalar(
            select(Case)
            .options(selectinload(Case.gemology_records), selectinload(Case.evidences))
            .where(Case.id == case.id)
        )
        session.expunge_all()
        return loaded
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_case(case_id: str) -> Case | None:
    session = _session()
    try:
        case = session.scalar(
            select(Case)
            .options(selectinload(Case.gemology_records), selectinload(Case.evidences))
            .where(Case.id == case_id)
        )
        if case is not None:
            session.expunge_all()
        return case
    finally:
        session.close()


def list_cases() -> list[Case]:
    with SessionLocal() as session:
        cases = list(
            session.scalars(
                select(Case)
                .options(selectinload(Case.gemology_records), selectinload(Case.evidences))
                .order_by(Case.created_at.desc())
            )
        )
        session.expunge_all()
        return cases


def delete_case(case_id: str) -> bool:
    session = _session()
    try:
        case = session.get(Case, case_id)
        if case is None:
            return False
        session.delete(case)
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def save_gemology(record: GemologyData) -> GemologyData:
    session = _session()
    try:
        stored = session.merge(record)
        session.commit()
        session.refresh(stored)
        session.expunge(stored)
        return stored
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def save_evidence(record: Evidence) -> Evidence:
    session = _session()
    try:
        stored = session.merge(record)
        session.commit()
        session.refresh(stored)
        session.expunge(stored)
        return stored
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def create_client(
    name: str,
    email: str | None = None,
    company: str | None = None,
    phone: str | None = None,
    client_id: str | None = None,
) -> Client:
    cleaned = " ".join((name or "").split())
    if not cleaned:
        raise ValueError("El cliente necesita un nombre.")
    session = _session()
    try:
        client = Client(
            id=client_id or _new_id("CLT"),
            name=cleaned,
            email=(email or None),
            company=(company or None),
            phone=(phone or None),
        )
        session.add(client)
        session.commit()
        session.refresh(client)
        session.expunge(client)
        return client
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def list_clients() -> list[Client]:
    session = _session()
    try:
        clients = list(session.scalars(select(Client).order_by(Client.created_at.desc())))
        session.expunge_all()
        return clients
    finally:
        session.close()


def get_client(client_id: str) -> Client | None:
    session = _session()
    try:
        client = session.scalar(
            select(Client).options(selectinload(Client.lots)).where(Client.id == client_id)
        )
        if client is not None:
            session.expunge_all()
        return client
    finally:
        session.close()


def create_lot(
    title: str,
    client_id: str | None = None,
    reference_code: str | None = None,
    status: str = "open",
    lot_id: str | None = None,
) -> Lot:
    cleaned = " ".join((title or "").split())
    if not cleaned:
        raise ValueError("El lote necesita un título.")
    session = _session()
    try:
        lot = Lot(
            id=lot_id or _new_id("LOT"),
            client_id=client_id or None,
            title=cleaned,
            reference_code=(reference_code or None),
            status=status or "open",
        )
        session.add(lot)
        session.commit()
        session.refresh(lot)
        session.expunge(lot)
        return lot
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def list_lots() -> list[Lot]:
    session = _session()
    try:
        lots = list(
            session.scalars(
                select(Lot)
                .options(selectinload(Lot.client), selectinload(Lot.cases))
                .order_by(Lot.created_at.desc())
            )
        )
        session.expunge_all()
        return lots
    finally:
        session.close()


def get_lot(lot_id: str) -> Lot | None:
    session = _session()
    try:
        lot = session.scalar(
            select(Lot)
            .options(selectinload(Lot.client), selectinload(Lot.cases))
            .where(Lot.id == lot_id)
        )
        if lot is not None:
            session.expunge_all()
        return lot
    finally:
        session.close()


def assign_case_to_lot(case_id: str, lot_id: str | None) -> Case | None:
    """Vincula el expediente a un lote. lot_id vacío lo deja suelto."""
    session = _session()
    try:
        case = session.scalar(
            select(Case)
            .options(selectinload(Case.gemology_records), selectinload(Case.evidences))
            .where(Case.id == case_id)
        )
        if case is None:
            return None
        if lot_id:
            lot = session.get(Lot, lot_id)
            if lot is None:
                raise ValueError("El lote no existe.")
        case.lot_id = lot_id or None
        session.commit()
        session.refresh(case)
        session.expunge_all()
        return case
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _normalize_bucket_path(file_name: str) -> str:
    cleaned = str(file_name or "").lstrip("/")
    if cleaned.startswith("cases/"):
        return cleaned
    return f"cases/{cleaned}"


def _storage_bucket():
    return supabase.storage.from_(SUPABASE_BUCKET)


def _clean_storage_path_for_signing(storage_path: str) -> str:
    """Ruta de objeto dentro del bucket, sin prefijo duplicado del bucket."""
    path = (storage_path or "").strip().lstrip("/")
    if not path:
        return ""
    bucket = (SUPABASE_BUCKET or "evidence").strip("/")
    prefixes = (f"{bucket}/", "evidence/", "evidences/")
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if path.startswith(prefix):
                path = path[len(prefix):]
                changed = True
                break
    return path


def upload_evidence_to_storage(local_path: str, file_name: str) -> str:
    """Sube la foto al bucket privado SUPABASE_BUCKET y devuelve la ruta interna del objeto."""
    path = Path(local_path)
    object_path = _normalize_bucket_path(file_name)
    content_type = _CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")
    payload = path.read_bytes()
    bucket = _storage_bucket()
    bucket.upload(
        object_path,
        payload,
        file_options={"content-type": content_type, "upsert": "true"},
    )
    return object_path


def get_signed_evidence_url(storage_path: str, expires_in: int = 3600) -> str:
    """Devuelve una URL firmada temporal para rutas del bucket privado (no público)."""
    raw = (storage_path or "").strip()
    if not raw:
        return ""
    if raw.lower().startswith("http"):
        return raw
    clean_path = _clean_storage_path_for_signing(raw)
    if not clean_path:
        print(f"[get_signed_evidence_url] Ruta vacía tras limpiar: raw='{raw}'", flush=True)
        return ""
    try:
        res = _storage_bucket().create_signed_url(clean_path, expires_in)
        if isinstance(res, dict):
            url = res.get("signedURL") or res.get("signedUrl") or res.get("signed_url") or ""
        else:
            url = (
                getattr(res, "signedURL", None)
                or getattr(res, "signedUrl", None)
                or getattr(res, "signed_url", None)
                or ""
            )
        url = str(url or "").strip()
        if not url:
            print(
                f"[get_signed_evidence_url] Sin URL firmada para path='{clean_path}' (respuesta: {res!r})",
                flush=True,
            )
            return ""
        if url.startswith("/"):
            base = (SUPABASE_URL or "").rstrip("/")
            if base:
                url = f"{base}{url}"
        return url
    except Exception as exc:
        print(f"[get_signed_evidence_url] Fallo firmando path='{clean_path}': {exc}", flush=True)
        return ""


_EMBEDDING_DIM = 768
_EMBEDDING_MODEL_NAME = "gemini-embedding-001"
_genai_embed_client = None


def _embedding_genai_client():
    global _genai_embed_client
    if _genai_embed_client is not None:
        return _genai_embed_client
    try:
        from google import genai
        from src.research.ai_agent import resolve_gemini_api_key

        api_key = resolve_gemini_api_key()
        _genai_embed_client = genai.Client(api_key=api_key) if api_key else genai.Client()
        return _genai_embed_client
    except Exception as exc:
        print(f"[RAG] Cliente de embeddings no disponible: {exc}", flush=True)
        return None


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{float(v):.8f}" for v in values) + "]"


def generate_text_embedding(text: str) -> list[float]:
    """Vectoriza texto con Google GenAI (768d). Devuelve [] si falla."""
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    client = _embedding_genai_client()
    if client is None:
        return []
    from google.genai import types

    truncated = cleaned[:12000]
    try:
        response = client.models.embed_content(
            model=_EMBEDDING_MODEL_NAME,
            contents=truncated,
            config=types.EmbedContentConfig(output_dimensionality=_EMBEDDING_DIM),
        )
        vectors = getattr(response, "embeddings", None) or []
        if vectors:
            values = getattr(vectors[0], "values", None) or []
            if len(values) == _EMBEDDING_DIM:
                return [float(v) for v in values]
        single = getattr(response, "embedding", None)
        if single is not None:
            values = getattr(single, "values", None) or []
            if len(values) == _EMBEDDING_DIM:
                return [float(v) for v in values]
    except Exception as exc:
        print(f"[RAG] Embedding {_EMBEDDING_MODEL_NAME} falló: {exc}", flush=True)
    return []


def compose_case_summary_for_embedding(case_id: str, metadata: dict, dictamen_text: str) -> str:
    """Texto consolidado para memoria vectorial de galería."""
    meta = dict(metadata or {})
    forensic = dict(meta.get("forensic_report") or {})
    market = dict(meta.get("market_valuation_report") or {})
    logistics = dict(meta.get("logistics_arbitrage_report") or {})
    materials = ", ".join(forensic.get("primary_materials") or [])
    attrs = "; ".join(f"{k}: {v}" for k, v in (forensic.get("key_attributes") or {}).items())
    lines = [
        f"EXPEDIENTE {case_id}",
        f"Marca: {meta.get('custom_brand') or '—'}",
        f"Título: {meta.get('custom_title') or meta.get('object_description') or '—'}",
        f"Taxonomía: {meta.get('domain_taxonomy') or forensic.get('taxonomy_key') or '—'}",
        f"Categoría forense: {forensic.get('category_name') or '—'}",
        f"Materiales: {materials or '—'}",
        f"Pureza/grado: {forensic.get('purity_or_grade') or '—'}",
        f"Peso/volumen: {forensic.get('estimated_weight_or_volume') or '—'}",
        f"Atributos: {attrs or '—'}",
        f"Resumen forense: {(forensic.get('technical_summary') or '')[:1200]}",
        f"Tendencia demanda (mercado): {market.get('demand_trend') or '—'}",
        f"Rango valoración CH: {market.get('estimated_value_low')} - {market.get('estimated_value_high')} {market.get('currency') or 'EUR'}",
        f"HS logístico: {logistics.get('hs_code_estimate') or '—'} · Hub: {logistics.get('recommended_primary_hub') or '—'}",
        f"Dictamen (extracto): {(dictamen_text or '')[:2500]}",
    ]
    return "\n".join(line for line in lines if line)


def upsert_case_embedding(case_id: str, taxonomy_key: str, summary_text: str) -> bool:
    """Genera vector y persiste memoria RAG del expediente."""
    from datetime import datetime, timezone

    cid = (case_id or "").strip()
    summary = (summary_text or "").strip()
    if not cid or not summary:
        return False
    vector = generate_text_embedding(summary)
    if len(vector) != _EMBEDDING_DIM:
        print(f"[RAG] Embedding vacío o dimensión inválida para case {cid}", flush=True)
        return False

    taxonomy = normalize_snake_key(taxonomy_key) if (taxonomy_key or "").strip() else "GENERAL"
    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        row = session.get(CaseEmbedding, cid)
        if row is None:
            row = CaseEmbedding(
                case_id=cid,
                taxonomy_key=taxonomy,
                summary_text=summary,
                embedding=vector,
                updated_at=now,
            )
            session.add(row)
        else:
            row.taxonomy_key = taxonomy
            row.summary_text = summary
            row.embedding = vector
            row.updated_at = now
        session.commit()
    print(f"[RAG] Expediente {cid} indexado en case_embeddings.", flush=True)
    return True


def search_similar_cases(
    query_text: str,
    limit: int = 3,
    exclude_case_id: str | None = None,
) -> list[dict]:
    """Búsqueda por similitud coseno en memoria vectorial de expedientes."""
    cleaned = (query_text or "").strip()
    if not cleaned:
        return []
    query_vector = generate_text_embedding(cleaned)
    if len(query_vector) != _EMBEDDING_DIM:
        return []

    q_literal = _vector_literal(query_vector)
    exclude = (exclude_case_id or "").strip() or None
    sql = text(
        """
        SELECT
            ce.case_id,
            ce.taxonomy_key,
            ce.summary_text,
            c.custom_brand,
            c.custom_title,
            c.object_description,
            c.dictamen_text,
            1 - (ce.embedding <=> CAST(:query_vec AS vector)) AS similarity
        FROM case_embeddings ce
        JOIN cases c ON c.id = ce.case_id
        WHERE (:exclude_id IS NULL OR ce.case_id <> :exclude_id)
        ORDER BY ce.embedding <=> CAST(:query_vec AS vector)
        LIMIT :result_limit
        """
    )

    try:
        with SessionLocal() as session:
            rows = session.execute(
                sql,
                {
                    "query_vec": q_literal,
                    "exclude_id": exclude,
                    "result_limit": max(1, int(limit)),
                },
            ).mappings()
            results = []
            for row in rows:
                title = row.get("custom_title") or row.get("object_description") or row.get("case_id")
                results.append(
                    {
                        "case_id": row.get("case_id"),
                        "taxonomy_key": row.get("taxonomy_key"),
                        "brand": row.get("custom_brand") or "",
                        "title": title or "",
                        "summary_text": row.get("summary_text") or "",
                        "dictamen_excerpt": (row.get("dictamen_text") or "")[:1200],
                        "similarity": float(row.get("similarity") or 0.0),
                    }
                )
            return results
    except Exception as exc:
        print(f"[RAG] search_similar_cases falló: {exc}", flush=True)
        return []
