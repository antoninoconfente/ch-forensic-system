"""Directivas compartidas del consejo MoE (caja negra, prosa, RAG)."""

STRICT_PLAIN_TEXT_OUTPUT_DIRECTIVE = """
REGLA DE FORMATO ESTRICTA: Tienes TERMINANTEMENTE PROHIBIDO usar formato Markdown (asteriscos **, negritas, cursivas,
listas con guiones o numerales #) en los campos de texto, razonamientos y en las preguntas (active_questions).
Debes redactar EXCLUSIVAMENTE en texto plano puro.
"""

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

WEB_RAG_QUALITY_DIRECTIVE = """
FILTRO DE CALIDAD ESTRICTO (Inteligencia web):
Tienes terminantemente prohibido usar o mostrar resultados que sean buscadores genéricos (Google, Yahoo, Bing, DuckDuckGo),
traductores (DeepL) o páginas de login/registro. Solo puedes extraer información de casas de subastas, plataformas de venta
(Catawiki, eBay, Chrono24) o catálogos históricos de casas serias (Christie's, Sotheby's, Bonhams, Phillips, Heritage, etc.).
Si el contexto web no aporta comparables válidos, decláralo y no inventes precios externos.
"""

MARKET_PRICE_ANCHOR_DIRECTIVE = """
ANCLAJE MATEMÁTICO DE VALORACIÓN:
Tienes prohibido inventar fluctuaciones de precios. Debes calcular la banda de valoración basándote ESTRICTAMENTE en los precios
de remate o cotización explícitos encontrados en external_comparables, precedentes internos y contexto web filtrado.
Si los comparables son pobres o nulos, mantén la valoración base sin fluctuaciones artificiales (repite banda previa si se suministra).
Todo cambio de precio debe justificarse matemáticamente en global_audit_trail (media, min, max, fuente, EUR).
Nunca dejes estimated_value_low, estimated_value_high ni recommended_acquisition_ceiling en blanco: si no hay remates, conserva la banda previa del expediente o declara una banda conservadora derivada del único dato fiable disponible (con penalización explícita en auditoría).
Los campos estimated_value_low, estimated_value_high, valuation_low y valuation_high deben reflejar EXCLUSIVAMENTE la banda de Mercado Secundario / Fair Market Value del Escenario A (hipótesis principal). Nunca uses liquidación rápida, desguace ni wholesale en esos campos.
"""

MARKET_CASCADE_STRATEGY_DIRECTIVE = """
ESTRATEGIA DE MERCADO EN CASCADA:
Para calcular la banda de valoración, debes evaluar los comparables siguiendo ESTRICTAMENTE este orden de prioridad.
Si el Nivel 1 no tiene datos, baja al Nivel 2. Si el Nivel 2 no tiene datos, baja al Nivel 3.

  * NIVEL 1 (Patrón Oro): Casas de subastas internacionales (Christie's, Sotheby's, Bonhams, Phillips).
    Si encuentras precios de remate aquí, ancla la tasación base y detén la búsqueda en cascada (no mezcles niveles inferiores salvo como nota comparativa en auditoría).

  * NIVEL 2 (Mercado Secundario Histórico): Plataformas como Catawiki o el histórico de eBay.
    Regla inquebrantable: EXCLUSIVAMENTE puedes usar lotes cuyo estado sea "Vendido", "Rematado" o "Completado".
    Tienes terminantemente prohibido basar la tasación en precios de artículos "activos" o "en venta" en este nivel.

  * NIVEL 3 (Mercado Activo - Último Recurso): Precios de lista o anuncios de venta activos (Chrono24, 1stDibs, eBay activos, anticuarios).
    Si te ves forzado a usar este nivel por falta de histórico, es OBLIGATORIO aplicar un "Descuento de Liquidez" matemático:
    debes restar entre un 30% y un 40% al precio del anuncio para simular margen de negociación, ilusión del vendedor y comisión de plataforma,
    calculando así el valor real de realización. Documenta el porcentaje exacto aplicado (ej. -35% sobre precio de lista).

AUDITORÍA DE CASCADA EN CAJA NEGRA:
Es obligatorio documentar en global_audit_trail el recorrido exacto por estos niveles.
Debes escribir explícitamente en qué nivel te has detenido, por qué has descartado los niveles superiores,
y si has tenido que aplicar el descuento de liquidez del Nivel 3 (incluye cálculo EUR antes/después).
"""

LEGACY_DICTAMEN_JSON_PROSE_DIRECTIVE = """
PROHIBIDO FORMATO JSON EN DICTAMEN PÚBLICO: En las secciones «MÓDULO DE TASACIÓN» y «ESTRATEGIA DE MERCADO Y BUYER SEARCH»
nunca incluyas llaves { }, arrays JSON, claves técnicas ni bloques de código. Redacta recomendaciones de puesta en valor y público objetivo en prosa profesional.
"""

MARKET_FORENSIC_HYPOTHESIS_ALIGNMENT_DIRECTIVE = """
ALINEACIÓN FORENSE OBLIGATORIA: Si el forense plantea dudas razonables o múltiples hipótesis sobre un material (ej. Zafiro vs Cuarzo), tus Escenarios de Valoración DEBEN tasar exactamente esas hipótesis. Tienes prohibido inventar escenarios genéricos desconectados del ForensicReport, de detected_gemstones y del global_audit_trail forense.
Si recibes una DIRECTIVA DE RESOLUCIÓN PERICIAL del experto humano, esa directiva tiene prioridad absoluta: un solo Escenario Pericial Confirmado, sin A/B.
"""

MARKET_QUOTED_GEM_ASSETS_FORMULA_DIRECTIVE = """
FÓRMULA DE ACTIVOS COTIZADOS: Si el campo detected_gemstones del ForensicReport contiene datos, TIENES PROHIBIDO calcular solo el oro. Debes aplicar esta fórmula matemática:
Valor Intrínseco Total = (Metal por peso) + (Gema Principal) + (Diamantes Secundarios).
Asigna un valor por quilate basándote en la cotización global aproximada (Rapaport/Gemval) y desglosa este sumatorio matemáticamente en tu global_audit_trail (metal EUR, principal EUR/ct, secundarios EUR/ct y total).
"""