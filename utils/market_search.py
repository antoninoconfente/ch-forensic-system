"""Construcción de queries web para comparables (marca + modelo)."""

from __future__ import annotations

import re

from agents.schemas import ForensicReport

_GENERIC_OBJECT_WORDS = frozenset(
    {
        "pieza",
        "objeto",
        "analizada",
        "visión",
        "artificial",
        "peritada",
        "sin",
        "notas",
        "adicionales",
    }
)

_IRRELEVANT_SNIPPETS = re.compile(
    r"utility\s+bill|electricity|power\s+bill|water\s+bill|internet\s+bill|phone\s+bill",
    re.IGNORECASE,
)

_BLOCKED_DOMAINS = re.compile(
    r"(?:^|//)(?:www\.)?"
    r"(?:google\.[a-z.]+|yahoo\.[a-z.]+|bing\.com|duckduckgo\.com|deepl\.com|translate\.google|"
    r"accounts\.google|login\.|signin\.|auth\.|facebook\.com|twitter\.com|x\.com)",
    re.IGNORECASE,
)

_TRUSTED_MARKET_HINTS = re.compile(
    r"catawiki|ebay\.|chrono24|christies|sothebys|bonhams|phillips|heritageauctions|"
    r"liveauctioneers|invaluable|1stdibs|barnebys|dorotheum|artcurial|lempertz|"
    r"subasta|auction|hammer price|lot\s+#|precio\s+de\s+salida",
    re.IGNORECASE,
)


def _brand_model_tokens(
    object_description: str,
    forensic_report: ForensicReport | None = None,
) -> str:
    tokens: list[str] = []
    if forensic_report is not None:
        for chunk in (
            forensic_report.category_name,
            forensic_report.taxonomy_key.replace("_", " "),
            " ".join(forensic_report.primary_materials[:2]),
        ):
            chunk = str(chunk or "").strip()
            if chunk and chunk.casefold() not in _GENERIC_OBJECT_WORDS:
                tokens.append(chunk)
        attrs = forensic_report.key_attributes or {}
        for key in ("brand", "maker", "marca", "model", "modelo", "reference", "referencia"):
            val = str(attrs.get(key) or "").strip()
            if val:
                tokens.append(val)

    desc = re.sub(r"\s+", " ", str(object_description or "").strip())
    if desc:
        for word in desc.split()[:8]:
            w = word.strip(".,;:")
            if not w or w.casefold() in _GENERIC_OBJECT_WORDS:
                continue
            if len(w) < 2:
                continue
            tokens.append(w)

    seen: set[str] = set()
    ordered: list[str] = []
    for t in tokens:
        key = t.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(t)
    return " ".join(ordered[:6]).strip()


def build_comparable_web_queries(
    object_description: str,
    forensic_report: ForensicReport | None = None,
) -> list[str]:
    """Solo Marca + Modelo + subasta/precio — sin queries vacías ni notas largas."""
    core = _brand_model_tokens(object_description, forensic_report)
    if not core or len(core) < 4:
        return []
    return [
        f'"{core}" catawiki subasta',
        f'"{core}" site:chrono24.com',
        f'"{core}" ebay sold auction',
        f'"{core}" hammer price christies OR sothebys OR bonhams",
    ]


def filter_relevant_web_results(results: list[dict]) -> list[dict]:
    """Descarta buscadores, traductores y login; solo plataformas de mercado confiables."""
    filtered: list[dict] = []
    for item in results or []:
        href = str(item.get("href") or "")
        title = str(item.get("title") or "")
        body = str(item.get("body") or "")
        blob = f"{title} {body} {href}"
        if _IRRELEVANT_SNIPPETS.search(blob):
            continue
        if _BLOCKED_DOMAINS.search(href) or _BLOCKED_DOMAINS.search(blob):
            continue
        if re.search(r"\b(übersetzer|translator|traductor)\b", blob, re.IGNORECASE):
            continue
        if not _TRUSTED_MARKET_HINTS.search(blob):
            continue
        filtered.append(item)
    return filtered