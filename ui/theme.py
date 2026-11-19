import html
import os

from nicegui import ui

# ==========================================
# MOODBOARD ARCHITECTURAL & MAGAZINE CSS
# ==========================================
EDITORIAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400&family=Inter:wght@300;400;500;600&display=swap');

:root {
    --paper-bg: #F3EFE6;
    --card-cream: #F3EFE6;
    --ink: #141413;
    --muted: #625E57;
    --hairline: #B8B2A4;
    --dark-rule: #141413;
}

body, .q-page, .q-layout {
    background-color: var(--paper-bg) !important;
    color: var(--ink) !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    -webkit-font-smoothing: antialiased;
}

h1, h2, h3, h4, .editorial-serif {
    font-family: 'Cormorant Garamond', 'Georgia', serif !important;
    color: var(--ink) !important;
    font-weight: 400 !important;
    letter-spacing: -0.015em !important;
}

.masthead-title {
    font-family: 'Cormorant Garamond', Georgia, serif !important;
    font-size: clamp(2.8rem, 5.5vw, 4.8rem);
    line-height: 0.94;
    letter-spacing: -0.02em;
    text-transform: uppercase;
    color: var(--ink);
}

.micro-coord {
    font-family: 'Inter', sans-serif;
    font-size: 0.66rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--muted);
    font-weight: 500;
}

.editorial-btn {
    background-color: var(--paper-bg) !important;
    color: var(--ink) !important;
    border: 1px solid var(--ink) !important;
    border-radius: 0 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.68rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.15em !important;
    text-transform: uppercase !important;
    padding: 10px 22px !important;
    cursor: pointer !important;
    transition: background-color 0.15s ease !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
}
.editorial-btn:hover {
    background-color: #E5DFD2 !important;
}

.editorial-btn-primary {
    background-color: var(--ink) !important;
    color: var(--paper-bg) !important;
    border: 1px solid var(--ink) !important;
}
.editorial-btn-primary:hover {
    background-color: #2a2a28 !important;
}

.editorial-status-badge {
    display: inline-block;
    margin-top: 8px;
    padding: 5px 12px;
    border: 1px solid var(--hairline);
    font-family: 'Inter', sans-serif;
    font-size: 0.62rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    font-weight: 500;
    color: var(--muted);
}
.editorial-status-badge--draft {
    border-color: #8c6d28;
    color: #8c6d28;
}
.editorial-status-badge--archived {
    border-color: var(--hairline);
    color: var(--muted);
}

.editorial-btn-sm {
    background-color: transparent !important;
    color: var(--ink) !important;
    border: none !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.66rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.15em !important;
    text-transform: uppercase !important;
    padding: 4px 8px !important;
    cursor: pointer !important;
}
.editorial-btn-sm:hover {
    text-decoration: underline !important;
}

.editorial-tab {
    background-color: transparent !important;
    color: var(--muted) !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.7rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.16em !important;
    text-transform: uppercase !important;
    padding: 14px 24px !important;
    cursor: pointer !important;
    transition: all 0.15s ease !important;
}
.editorial-tab:hover {
    color: var(--ink) !important;
}
.editorial-tab-active {
    color: var(--ink) !important;
    border-bottom: 2px solid var(--ink) !important;
    font-weight: 600 !important;
}

.editorial-uploader,
.editorial-uploader .q-uploader__header,
.editorial-uploader .q-uploader__list {
    background-color: var(--paper-bg) !important;
    background: var(--paper-bg) !important;
    color: var(--ink) !important;
}
.editorial-uploader {
    border: 1px solid var(--ink) !important;
    border-radius: 0 !important;
    box-shadow: none !important;
}
.editorial-uploader .q-uploader__header {
    border-bottom: 1px solid var(--ink) !important;
}
.editorial-uploader .q-btn {
    color: var(--ink) !important;
}

.catalog-card {
    background-color: var(--card-cream) !important;
    border: 1px solid var(--ink) !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    padding: 18px !important;
    height: 495px !important;
    display: flex !important;
    flex-direction: column !important;
    justify-content: space-between !important;
}
.catalog-img-frame {
    width: 100%;
    height: 265px;
    border: 1px solid var(--hairline);
    overflow: hidden;
    background-color: #EAE4D7;
    flex-shrink: 0;
}
.catalog-img-frame img,
.catalog-img-frame .q-img,
.catalog-img-frame .q-img__image {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
}
.catalog-roman {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 0.85rem;
    color: var(--ink);
    margin-top: 10px;
}
.catalog-brand {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 0.76rem;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    text-align: center;
    color: var(--ink);
    margin: 2px 0 8px 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.catalog-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 10px;
    border-bottom: 1px solid var(--ink);
    padding-bottom: 7px;
    margin-bottom: 8px;
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 1.04rem;
    color: var(--ink);
}
.catalog-title-text {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-weight: 500;
}
.catalog-price-text {
    flex-shrink: 0;
    font-size: 0.92rem;
}
.catalog-excerpt {
    font-size: 0.72rem;
    color: var(--muted);
    line-height: 1.45;
    height: 2.9em;
    overflow: hidden;
    margin: 0;
}

.spec-table {
    width: 100%;
    border-top: 1px solid var(--ink);
}
.spec-row {
    display: grid;
    grid-template-columns: 165px 1fr;
    gap: 16px;
    padding: 10px 0;
    border-bottom: 1px solid var(--ink);
    align-items: baseline;
}
.spec-label {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--muted);
}
.spec-value {
    font-size: 0.84rem;
    font-weight: 500;
    color: var(--ink);
}

.editorial-reader {
    max-width: 960px;
    font-size: 0.92rem;
    line-height: 1.72;
    color: var(--ink);
}
.editorial-reader h1, .editorial-reader h2, .editorial-reader h3 {
    font-family: 'Cormorant Garamond', Georgia, serif !important;
    font-size: 1.55rem !important;
    margin-top: 1.5rem !important;
    margin-bottom: 0.6rem !important;
    border-bottom: 1px solid var(--ink);
    padding-bottom: 6px;
}
.editorial-reader table {
    width: 100%;
    border-collapse: collapse;
    margin: 1.2rem 0;
    font-size: 0.84rem;
}
.editorial-reader th, .editorial-reader td {
    border: 1px solid var(--ink);
    padding: 10px 12px;
    text-align: left;
    vertical-align: top;
}
.editorial-reader th {
    background-color: #EAE4D7;
    font-size: 0.7rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
}
.editorial-reader hr {
    border: none;
    border-top: 1px solid var(--ink);
    margin: 2rem 0;
}

.thumb-strip-item {
    width: 140px;
    flex-shrink: 0;
    cursor: pointer;
}
.thumb-frame {
    width: 140px;
    height: 140px;
    border: 1px solid var(--ink);
    overflow: hidden;
    background-color: #EAE4D7;
}
.thumb-frame img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    transition: transform 0.2s ease;
}
.thumb-frame:hover img {
    transform: scale(1.04);
}

.audit-box, .question-card {
    background-color: var(--paper-bg) !important;
    border: 1px solid var(--ink) !important;
    border-radius: 0 !important;
    padding: 1.1rem !important;
    margin-bottom: 0.75rem;
}

.human-evidence-box {
    background-color: #ECE6D8 !important;
    border: 1px solid var(--ink) !important;
    padding: 1.25rem !important;
    margin-bottom: 1rem;
}

.blueprint-box {
    background-color: #F7F4EC;
    border: 1px solid var(--ink);
    padding: 10px 12px;
    margin: 4px 0 4px 0;
}

.lot-brief {
    background-color: var(--paper-bg);
    border-top: 2px solid var(--ink);
    border-bottom: 1px solid var(--ink);
    padding: 1.5rem 0;
    margin: 0.5rem 0 1rem;
    width: 100%;
}
.lot-brief-top {
    display: flex;
    justify-content: space-between;
    gap: 24px;
    align-items: flex-end;
    flex-wrap: wrap;
}
.lot-kicker {
    margin: 0;
    font-size: 0.68rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--muted);
}
.lot-title {
    margin: 6px 0 0 0;
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 1.9rem;
    font-weight: 400;
    color: var(--ink);
}
.lot-count {
    margin: 6px 0 0 0;
    font-size: 0.78rem;
    color: var(--muted);
}
.lot-total { text-align: right; min-width: 180px; }
.lot-figure {
    margin: 4px 0 0 0;
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 2.1rem;
    color: var(--ink);
}
.lot-metrics {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 12px;
    margin-top: 18px;
    padding-top: 14px;
    border-top: 1px solid var(--ink);
}
.lot-metrics span {
    display: block;
    font-size: 0.68rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--muted);
}
.lot-metrics strong {
    display: block;
    margin-top: 4px;
    font-weight: 500;
    font-size: 0.95rem;
}
.lot-exit {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 18px;
    margin-top: 16px;
}
.lot-exit p { margin-top: 4px; color: var(--ink); font-size: 0.88rem; line-height: 1.4; }
.lot-reason {
    margin: 14px 0 0 0;
    color: var(--muted);
    font-size: 0.88rem;
    line-height: 1.45;
}
</style>
"""


# ==========================================


def _web_img_src(local_path: str) -> str:
    if not local_path:
        return ""
    norm = os.path.normpath(local_path).replace("\\", "/")
    if norm.startswith("data/"):
        return "/" + norm
    idx = norm.find("/data/")
    if idx != -1:
        return norm[idx:]
    return norm


def editorial_button(label: str, on_click, small: bool = False, extra_classes: str = ""):
    cls = "editorial-btn-sm" if small else "editorial-btn"
    if extra_classes:
        cls = f"{cls} {extra_classes}"
    btn = ui.element("button").classes(cls)
    with btn:
        ui.html(f"<span>{html.escape(label)}</span>")
    btn.on("click", on_click)
    return btn
