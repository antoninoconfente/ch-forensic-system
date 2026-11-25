"""Directivas compartidas del consejo MoE (caja negra, prosa, RAG)."""

GLOBAL_AUDIT_TRAIL_JSON_HINT = """
global_audit_trail: lista de strings (puede iniciar vacía). Cada línea documenta una decisión técnica o de mercado con impacto explícito.
"""

MODO_AUDITOR_MARKET_DIRECTIVE = """
MODO AUDITOR (global_audit_trail — obligatorio):
Registra en global_audit_trail cada decisión de tasación: bandas de precio elegidas, precedentes internos que pesaron, comparables web descartados o aceptados,
tendencia de demanda y techo de adquisición. Explica el porqué en prosa de auditoría interna (EUR, %, fuentes). No dupliques este razonamiento en pricing_rationale orientado al usuario.
"""

MODO_AUDITOR_LOGISTICS_DIRECTIVE = """
MODO AUDITOR (global_audit_trail — obligatorio):
Registra en global_audit_trail cada decisión logística y aduanera: HS estimado, alertas CITES/patrimonio, hubs comparados, reglas arancelarias aplicadas,
márgenes netos por ruta y precio máximo de compra. Justifica descartes de rutas y riesgos regulatorios. No dupliques en net_margin_rationale público.
"""

MARKET_JSON_PROSE_DIRECTIVE = """
PROHIBIDO FORMATO JSON: Nunca devuelvas código, llaves { }, corchetes de listas JSON, ni fragmentos tipo "user_prompt" dentro de campos de texto plano
(pricing_rationale, demand_trend, similarity_or_relevance, notes en comparables, price_estimate). Redacta siempre en prosa profesional en español.
"""

PRECEDENTS_NATURAL_LANGUAGE_DIRECTIVE = """
FILTRO DE METADATOS (precedentes internos):
Tienes terminantemente prohibido imprimir variables de código, IDs de base de datos (case_id, uuid), métricas de similitud (sim=, 0.790, similarity)
o JSON crudo al describir precedentes en pricing_rationale, notes, similarity_or_relevance o global_audit_trail.
Sintetiza cada precedente en lenguaje natural (ej.: «Pieza similar de la galería CH con tasación histórica en torno a X EUR»).
"""

LEGACY_DICTAMEN_JSON_PROSE_DIRECTIVE = """
PROHIBIDO FORMATO JSON EN DICTAMEN PÚBLICO: En las secciones «MÓDULO DE TASACIÓN» y «ESTRATEGIA DE MERCADO Y BUYER SEARCH»
nunca incluyas llaves { }, arrays JSON, claves técnicas ni bloques de código. Redacta recomendaciones de puesta en valor y público objetivo en prosa profesional.
"""