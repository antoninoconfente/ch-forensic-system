"""Utilidades de presentación editorial para dictámenes Markdown."""

from __future__ import annotations

import re

_NUMBERED_HEADER = re.compile(
    r"^(?P<level>#{2,3})\s*(?P<num>\d+)(?P<sep>[\.\)])\s*(?P<title>.+?)\s*$",
    re.MULTILINE,
)


def renumber_markdown_headers(text: str) -> str:
    """
    Renumera cabeceras ``## N. Título`` / ``### N) Título`` en orden secuencial (1, 2, 3…).
    Conserva el nivel (#/##) y el separador (. o )).
    """
    if not (text or "").strip():
        return text or ""

    counter = 0

    def _repl(match: re.Match) -> str:
        nonlocal counter
        counter += 1
        return (
            f"{match.group('level')} {counter}{match.group('sep')} "
            f"{match.group('title').strip()}"
        )

    return _NUMBERED_HEADER.sub(_repl, text)