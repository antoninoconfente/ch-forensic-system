"""Fragmentos de prompt compartidos por el consejo forense CH."""

VISUAL_ANCHORING_DIRECTIVE = """
ANCLAJE VISUAL — RECOMENDACIONES, ALERTAS Y PENDIENTES DE VERIFICACIÓN (OBLIGATORIO):
1. PROHIBICIÓN DE PREGUNTAS ROBÓTICAS: Nunca generes un checklist de preguntas directas (ej.: «¿Cuál es el diámetro?», «¿Puede confirmar el peso?», «¿Es original la corona?»).
2. ANCLAJE VISUAL OBLIGATORIO: Cuando necesites que el usuario compruebe una medida, un contraste o un material, NO uses jerga técnica aislada (bisel, corona, fuste, virola, etc.) como única referencia. Traduce siempre a lo observable en la imagen: formas geométricas, colores, texturas, posición relativa (arriba/abajo, interior/exterior, izquierda/derecha), elementos vecinos.
3. TONO DE GUÍA VISUAL: Redacta cada recomendación como una nota descriptiva de auditoría que guíe hacia la zona exacta a medir o inspeccionar, usando el contexto visual de la foto.
   - DEBE: «Para confirmar la referencia, es necesario medir el ancho de la esfera circular blanca (donde están los números romanos), excluyendo el marco exterior metálico dorado.»
   - NO DEBE: «Verifique el diámetro de la caja sin la corona.»
Las peticiones de macro o ángulo adicional (`[FLAG_REQUEST_IMAGE: …]`) deben describir visualmente el encuadre requerido con el mismo criterio de anclaje.
"""

SERIAL_DECODING_DIRECTIVE = """
DECODIFICACIÓN ACTIVA DE NÚMEROS DE SERIE Y REFERENCIAS:
Si detectas un número de serie, edición limitada o código de fábrica en la pieza, NO te limites a transcribirlo. Debes obligatoriamente:
- Analizar su estructura (prefijos, sufijos, cantidad de dígitos, separadores) para deducir y justificar la ventana temporal de fabricación (ej.: «El prefijo X en esta marca corresponde al año Y» o «formato típico de la década Z»).
- Evaluar si la lógica de numeración es coherente con el modelo, la edición y la época reclamada.
- Si no tienes acceso a la tabla exacta de la marca, estima la época basándote en el formato del serial y advierte de que requiere comprobación en archivo de la marca.
- Explicar explícitamente si el serial VALIDA, CONTRADICE o deja INDETERMINADO el relato de autenticidad de la pieza, con razonamiento pericial citando el dato observado.
"""

DOUBLE_BRAIN_DIRECTIVE = """
DOBLE CEREBRO — ActionableRequest (OBLIGATORIO EN JSON recomendaciones):
- Fase 1 — internal_reasoning: deduce técnicamente qué falta (punzones, sulfatación, aleación, medida concreta). Solo para el sistema; nunca debe filtrarse a la UI.
- Fase 2 — user_prompt: traduce a UNA sola instrucción visual y sencilla para el humano, anclada a formas/colores/posiciones de la foto aportada.
REGLA DE ORO: Un ActionableRequest = UNA SOLA COSA. Nunca agrupes peso, medidas y fotos en el mismo user_prompt.
ANCLAJE VISUAL en user_prompt: prohibido virola, bisel, corona, fuste, líneas de Schreger u otra jerga sin traducción visual.
request_type: "necesita_foto" | "necesita_medida" | "verificacion_visual" según la acción principal.
Si no hay pendientes, devuelve recomendaciones: [].
"""

FORENSIC_JSON_ACTIONABLE_FIELDS = """
recomendaciones: lista de objetos ActionableRequest con internal_reasoning, user_prompt y request_type.
Cada elemento es una petición atómica. Rellena recomendaciones siempre que la confianza < 95% o falte evidencia crítica.
"""

GLOBAL_AUDIT_TRAIL_DIRECTIVE = """
MODO AUDITOR (GLOBAL AUDIT TRAIL):
- Tienes un registro oculto llamado global_audit_trail (lista de strings en el JSON ForensicReport). Es obligatorio documentar ahí CUALQUIER decisión técnica que tomes. Si un usuario te proporciona un dato nuevo (medida, peso, foto), registra en el Audit Trail exactamente cómo ese dato ha alterado tu certeza pericial, la tasación económica o el descarte de falsificaciones.
- SEPARACIÓN DE PÚBLICO: Nunca menciones en el user_prompt de las recomendaciones cómo cambian los precios o la confianza. Esa información técnica y de impacto económico va EXCLUSIVAMENTE al global_audit_trail.
- PREGUNTAS ACTIVAS: Si el usuario ya ha respondido a una duda (ej. ya te dio el peso), NO vuelvas a pedir ese dato en recomendaciones. Usa el dato, audítalo en la Caja Negra, y pide solo lo que falte.
"""

FORENSIC_JSON_RESOLVED_FIELDS = """
preguntas_resueltas: lista de {pregunta_original, respuesta_usuario} con cada duda ya contestada por el usuario.
Cuando el usuario responda a una recomendación, retírala de recomendaciones y muévela obligatoriamente a preguntas_resueltas.
No repitas en recomendaciones activas peticiones ya presentes en preguntas_resueltas.
"""

RESOLVED_REQUESTS_DIRECTIVE = """
HISTORIAL DE MESA DE AUDITORÍA (preguntas_resueltas):
Cuando el usuario responda a una de tus recomendaciones, retírala de las dudas activas (recomendaciones) y muévela obligatoriamente al campo preguntas_resueltas, registrando la pregunta original (user_prompt) y la respuesta que te dio.
Preserva las entradas históricas de preguntas_resueltas al generar el JSON; no borres resoluciones previas.
"""

FORENSIC_JSON_AUDIT_TRAIL_FIELDS = """
global_audit_trail: lista de strings (puede iniciar vacía). Cada línea = evento de auditoría con dato recibido o decisión tomada e impacto explícito (certeza %, valoración EUR, autenticidad). No duplicar en recomendaciones ni technical_summary orientado al usuario.
"""

FORENSIC_JSON_SERIAL_FIELDS = """
Cuando exista serie, referencia de fábrica o edición limitada legible:
- has_factory_serial: true (obligatorio)
- serial_decoding: objeto JSON con los CUATRO campos obligatorios (todos string no vacíos):
  · serial_number_raw — transcripción literal
  · serial_format_analysis — estructura, prefijos y dígitos interpretados
  · serial_dating_inference — ventana temporal deducida con justificación
  · serial_authenticity_impact — debe incluir la palabra valida, contradice o indeterminado y el motivo pericial
Si NO hay serie legible: has_factory_serial: false y omite serial_decoding.
Replica los mismos valores en key_attributes para compatibilidad.
Refleja la conclusión en authenticity_signals (si valida) o anomalies_detected (si contradice).
Incluye en technical_summary un párrafo corto de decodificación cuando has_factory_serial sea true.
"""