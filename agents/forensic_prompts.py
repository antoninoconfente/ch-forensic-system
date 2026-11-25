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