"""Fragmentos de prompt compartidos por el consejo forense CH."""

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