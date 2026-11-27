"""Notificaciones visibles en NiceGUI sin romper el pipeline en background."""

from __future__ import annotations


def notify_ai_error(message: str) -> None:
    text = str(message or "").strip() or "Error desconocido"
    payload = f"Error de conexión IA: {text}"
    try:
        from nicegui import ui

        ui.notify(payload, type="negative", position="top", timeout=10000)
    except Exception:
        print(f"[UI] {payload}", flush=True)


def notify_ai_errors(messages: list[str] | None) -> None:
    for msg in messages or []:
        if str(msg or "").strip():
            notify_ai_error(str(msg))