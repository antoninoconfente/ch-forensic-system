"""
Diccionario Maestro Global de Punzones, Contrastes y Casas de Alta Joyería
Estructura de referencia para blindar el Ojo Experto y eliminar sesgos geográficos.
"""

INTERNATIONAL_PUNCHMARKS_DB = {
    "jurisdictions": {
        "Japón": {
            "descripcion": "Sistema de la Japan Mint (Kokuyo) y orfebrería nipona.",
            "marcas_clave": ["K18", "750", "K24", "K14", "SV925", "SILVER 950", "ホールマーク", "Símbolos de la Ceca Nacional"],
            "marcas_maestras_destacadas": {
                "Mikimoto": "Logotipo de la ostra con la letra 'M' acompañado de marcas de pureza de la Japan Mint."
            }
        },
        "Italia": {
            "descripcion": "Sistema posterior a 1968 de marcas de fabricante y control provincial.",
            "marcas_clave": ["750", "18KT", "Estrella de 5 puntas", "Número de registro + sigla provincial (ej. 1 AR, 123 MI)"],
            "marcas_maestras_destacadas": {
                "Bulgari": "Firma tipográfica 'BVLGARI' grabada, numeración de serie y punzones oficiales italianos.",
                "Buccellati": "Técnicas de grabado manual (tulle, rayado), firma 'BUCCELLATI' y ceca de Milán/Roma."
            }
        },
        "Francia": {
            "descripcion": "Sistema estatal estricto de garantía y punzones de contraste histórico y moderno.",
            "marcas_clave": ["Cabeza de Águila (Oro 750)", "Concha (Oro 585)", "Trébol (Oro 375)", "Minerva (Plata)"],
            "marcas_maestras_destacadas": {
                "Cartier": "Punzones de maestro en rombo o cartela, número de serie único de 5-6 dígitos, cabeza de águila o perro.",
                "Van Cleef & Arpels": "Iniciales VCA, número de inventario de pieza y punzón de garantía francés.",
                "Boucheron / Chaumet": "Marcas de taller parisino y punzones de estado."
            }
        },
        "Reino Unido": {
            "descripcion": "Sistema histórico obligatorio de oficinas de contraste desde 1300.",
            "marcas_clave": ["Leopardo (Londres)", "Ancla (Birmingham)", "Rosa (Sheffield)", "Castillo (Edimburgo)", "Letra de fecha de datación"],
            "marcas_maestras_destacadas": {
                "Asprey / Garrard": "Sello de garantía real (Royal Warrant) y contrastes de oficinas oficiales."
            }
        },
        "Estados Unidos": {
            "descripcion": "Sistema de declaración de responsabilidad del fabricante (sin oficinas de contraste estatales obligatorias).",
            "marcas_clave": ["14K", "18K", "925", "Sterling", "Marcas registradas del fabricante"],
            "marcas_maestras_destacadas": {
                "Tiffany & Co.": "Firma 'TIFFANY & CO.', leyes en milésimas/quilates y códigos de diseñadores (Schlumberger, Peretti, Picasso)."
            }
        }
    },
    "leyes_y_aleaciones": {
        "oro": {
            "333": "8 Quilates (33.3% oro puro)",
            "375": "9 Quilates / K9 (37.5% oro puro)",
            "417": "10 Quilates / K10 (41.7% oro puro)",
            "585": "14 Quilates / K14 (58.5% oro puro)",
            "750": "18 Quilates / K18 (75.0% oro puro)",
            "916": "22 Quilates / K22 (91.6% oro puro)",
            "999": "24 Quilates / K24 (99.9% oro puro - Oro puro)"
        },
        "plata": {
            "800": "Plata de baja ley",
            "925": "Plata de ley / Sterling Silver",
            "950": "Plata alta pureza"
        },
        "platino": {
            "950": "Platino de alta pureza (95%)"
        },
        "advertencias_chapado": ["GP", "GF", "GEP", "HGE", "RGP", "EP", "Plaqué Or G"]
    }
}

def get_punchmarks_context_for_prompt() -> str:
    """Retorna un resumen estructurado del diccionario para inyectarlo en el system_instruction del agente."""
    return (
        "DICCIONARIO MAESTRO DE REFERENCIA INTERNACIONAL DE PUNZONES:\n"
        "- JAPÓN: Utiliza la Japan Mint con caracteres kanji/símbolos y purezas K18, 750. No confundir con Europa.\n"
        "- ITALIA: Sistema de cartela poligonal con número de registro de orfebre y sigla provincial (ej. AR, MI) + estrella.\n"
        "- FRANCIA: Contrastes estatales estrictos (Cabeza de Águila para Oro 750, Minerva para plata).\n"
        "- REINO UNIDO: Oficinas históricas (Leopardo en Londres, Ancla en Birmingham) y letras de fecha.\n"
        "- EEUU: Declaración de responsabilidad del fabricante (ej. Tiffany & Co., Sterling, 14K, 18K).\n"
        "REGLA CRÍTICA: Inspecciona los caracteres reales antes de asignar procedencia geográfica."
    )