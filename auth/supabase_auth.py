"""Sesiones Supabase Auth integradas con NiceGUI `app.storage.user`."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from nicegui import app
from supabase import create_client

from database.client import get_or_create_user_profile

load_dotenv()

_auth_client = None
SESSION_KEY = "auth_session"
ROLE_LABELS = {
    "admin": "ADMIN",
    "analyst": "ANALISTA",
    "viewer": "CONSULTA",
}


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def auth_bypass_local() -> bool:
    """Modo desarrollo: salta login si AUTH_BYPASS_LOCAL=true."""
    return _truthy(os.getenv("AUTH_BYPASS_LOCAL", "false"))


def get_auth_client():
    global _auth_client
    if _auth_client is not None:
        return _auth_client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError(
            "Configura SUPABASE_URL y SUPABASE_KEY en .env para habilitar el acceso privado."
        )
    _auth_client = create_client(url, key)
    return _auth_client


def _read_attr(source: Any, name: str) -> Any:
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(name)
    return getattr(source, name, None)


def _session_payload(session: Any, user: Any) -> dict:
    return {
        "access_token": _read_attr(session, "access_token"),
        "refresh_token": _read_attr(session, "refresh_token"),
        "expires_at": _read_attr(session, "expires_at"),
        "user": {
            "id": _read_attr(user, "id"),
            "email": _read_attr(user, "email"),
        },
    }


def _expected_invite_code() -> str:
    return (os.getenv("CH_INVITE_CODE") or "CH-ARCHIVE-2026").strip()


def _attach_profile_to_session(payload: dict) -> dict:
    user = payload.get("user") or {}
    user_id = user.get("id")
    email = user.get("email") or ""
    profile = get_or_create_user_profile(user_id, email)
    payload["role"] = profile.get("role") or "viewer"
    payload["email"] = profile.get("email") or email
    app.storage.user[SESSION_KEY] = payload
    return payload


def get_current_role() -> str:
    if auth_bypass_local():
        return "admin"
    session = app.storage.user.get(SESSION_KEY) or {}
    role = (session.get("role") or "viewer").strip().lower()
    return role if role in ROLE_LABELS else "viewer"


def role_display_label(role: str | None = None) -> str:
    return ROLE_LABELS.get((role or get_current_role()).lower(), "CONSULTA")


def can_investigate() -> bool:
    return get_current_role() in {"admin", "analyst"}


def can_save_expedient() -> bool:
    return get_current_role() in {"admin", "analyst"}


def can_delete_in_archive() -> bool:
    return get_current_role() == "admin"


def can_manage_lots() -> bool:
    return get_current_role() == "admin"


def sign_in_with_email(email: str, password: str) -> dict:
    """Autentica con Supabase Auth y persiste la sesión en `app.storage.user`."""
    cleaned_email = (email or "").strip()
    if not cleaned_email or not password:
        raise ValueError("Introduce email y contraseña válidos.")

    client = get_auth_client()
    try:
        response = client.auth.sign_in_with_password(
            {"email": cleaned_email, "password": password}
        )
    except Exception as exc:
        message = str(exc) or "Credenciales inválidas."
        if "invalid" in message.casefold() or "credentials" in message.casefold():
            raise ValueError("Credenciales inválidas. Verifique email y contraseña.") from exc
        raise ValueError(f"No se pudo iniciar sesión: {message}") from exc

    session = getattr(response, "session", None)
    user = getattr(response, "user", None)
    if session is None or user is None:
        raise ValueError("Credenciales inválidas. No se recibió sesión activa.")

    payload = _session_payload(session, user)
    if not payload.get("access_token"):
        raise ValueError("Credenciales inválidas. Token de acceso ausente.")

    return _attach_profile_to_session(payload)


def sign_up_with_email(email: str, password: str, invite_code: str) -> dict:
    """Registro con código de invitación y creación de perfil en PostgreSQL."""
    cleaned_email = (email or "").strip()
    if not cleaned_email or not password:
        raise ValueError("Introduce email y contraseña válidos.")
    if len(password) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres.")

    expected = _expected_invite_code()
    if (invite_code or "").strip() != expected:
        raise ValueError("Código de invitación inválido.")

    client = get_auth_client()
    try:
        response = client.auth.sign_up({"email": cleaned_email, "password": password})
    except Exception as exc:
        raise ValueError(f"No se pudo completar el registro: {exc}") from exc

    user = getattr(response, "user", None)
    user_id = _read_attr(user, "id")
    user_email = _read_attr(user, "email") or cleaned_email
    if not user_id:
        raise ValueError("Registro incompleto: no se recibió identificador de usuario.")

    get_or_create_user_profile(user_id, user_email)

    session = getattr(response, "session", None)
    if session is not None and _read_attr(session, "access_token"):
        payload = _session_payload(session, user)
        return _attach_profile_to_session(payload)

    return {"status": "pending_confirmation", "email": user_email, "user_id": user_id}


def sign_out(access_token: str | None = None) -> None:
    """Cierra sesión en Supabase y borra el almacenamiento de usuario."""
    stored = app.storage.user.get(SESSION_KEY) or {}
    token = access_token or stored.get("access_token")

    try:
        client = get_auth_client()
        refresh = stored.get("refresh_token")
        if token and refresh:
            client.auth.set_session(token, refresh)
        client.auth.sign_out()
    except Exception:
        pass
    finally:
        if SESSION_KEY in app.storage.user:
            del app.storage.user[SESSION_KEY]
        app.storage.user.pop("bypass_local", None)


def is_authenticated() -> bool:
    if auth_bypass_local():
        return True
    session = app.storage.user.get(SESSION_KEY) or {}
    return bool(session.get("access_token"))