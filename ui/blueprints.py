import html

# ==========================================
# CATÁLOGOS TÉCNICOS DE ALTA JOYERÍA
# ==========================================
JEWELRY_TYPES = ["Anillo / Sortija", "Pulsera / Brazalete", "Collar / Colgante", "Otro / Objeto"]

RING_SHANK_PROFILES = [
    "Tradicional (Aro redondo clásico)",
    "Estilo Europeo (Base cuadrada anti-giro)",
    "Catedral (Hombros elevados hacia cabeza)",
    "Straight (Banda recta uniforme)",
    "Tapered (Banda afilada hacia la piedra)",
    "Reverse Tapered (Ensanchada hacia la cabeza)",
    "Split Shank (Banda dividida en hombros)",
    "Bypass (Brazos cruzados envolventes)",
    "Media Alianza (Piedras en arco superior)",
    "Eternity / Sin fin (Piedras en todo el perímetro)",
]

SETTING_ARCHITECTURES = [
    "Canasta (4 o 6 garras con galería abierta)",
    "Espiga / V-Prong (Garras en V abiertas)",
    "Decorativo / Corona calada",
    "Biselado completo (Bezel cerrado)",
    "Semi-Biselado (Bezel abierto lateral)",
    "Barra / Carril / Canal (Channel setting)",
    "Pavé / Micro-pavé (Granos engastados en masa)",
]

GEM_CUT_CATALOG = [
    "Brillante Redondo",
    "Esmeralda / Octogonal",
    "Baguette / Carré (Escalonada)",
    "Princesa (Cuadrada)",
    "Oval",
    "Cojín (Cushion)",
    "Pera / Lágrima",
    "Marquesa / Navette",
    "Cabujón (Liso abombado)",
    "Talla Antigua / Rosa",
]

CUT_CARAT_FACTORS = {
    "Brillante Redondo": 0.0061,
    "Esmeralda / Octogonal": 0.0080,
    "Baguette / Carré (Escalonada)": 0.0085,
    "Princesa (Cuadrada)": 0.0083,
    "Oval": 0.0062,
    "Cojín (Cushion)": 0.0070,
    "Pera / Lágrima": 0.0059,
    "Marquesa / Navette": 0.0056,
    "Cabujón (Liso abombado)": 0.0075,
    "Talla Antigua / Rosa": 0.0064,
}

SPECIES_DENSITY_MULTIPLIER = {
    "Diamante": 1.00,
    "Esmeralda": 0.78,
    "Rubí": 1.14,
    "Zafiro": 1.14,
    "Coral / Opaca": 0.76,
    "Otra gema": 0.85,
}


def estimate_carats_from_mm(species: str, cut: str, count: int, length_mm: float, width_mm: float, depth_mm: float = 0.0) -> float:
    if count <= 0 or length_mm <= 0:
        return 0.0
    w = width_mm if width_mm > 0 else length_mm
    d = depth_mm if depth_mm > 0 else (w * 0.62)
    base_factor = CUT_CARAT_FACTORS.get(cut, 0.0065)
    density_mult = SPECIES_DENSITY_MULTIPLIER.get(species, 0.90)
    single_ct = length_mm * w * d * base_factor * density_mult
    return round(single_ct * count, 3)


def _discipline_metrology_svg_html(
    length_mm: float | None = None,
    width_mm: float | None = None,
    height_mm: float | None = None,
    diameter_mm: float | None = None,
    title: str = "",
) -> str:
    """Esquema de metrología genérica (no joyería) — caja técnica editorial."""
    l = length_mm or 0
    w = width_mm or 0
    h = height_mm or 0
    d = diameter_mm or 0
    label = html.escape(title or "Metrología de pieza")
    dim_txt = []
    if l:
        dim_txt.append(f"L={l:g} mm")
    if w:
        dim_txt.append(f"A={w:g} mm")
    if h:
        dim_txt.append(f"H={h:g} mm")
    if d:
        dim_txt.append(f"Ø={d:g} mm")
    dims = " · ".join(dim_txt) if dim_txt else "Cotas pendientes de verificación en mano"
    if d and not l:
        return f"""
        <svg viewBox="0 0 440 200" class="w-full max-w-lg" xmlns="http://www.w3.org/2000/svg">
            <rect x="8" y="8" width="424" height="184" fill="#F3EFE6" stroke="#141413" stroke-width="1"/>
            <text x="220" y="28" text-anchor="middle" font-size="9" font-family="Georgia, serif" fill="#141413">{label}</text>
            <ellipse cx="220" cy="105" rx="68" ry="68" fill="#EAE4D7" stroke="#141413" stroke-width="1.2"/>
            <line x1="152" y1="105" x2="288" y2="105" stroke="#8c6d28" stroke-width="0.8" stroke-dasharray="3 2"/>
            <text x="220" y="100" text-anchor="middle" font-size="8" fill="#625E57">{html.escape(dims)}</text>
        </svg>
        """
    return f"""
    <svg viewBox="0 0 440 200" class="w-full max-w-lg" xmlns="http://www.w3.org/2000/svg">
        <rect x="8" y="8" width="424" height="184" fill="#F3EFE6" stroke="#141413" stroke-width="1"/>
        <text x="220" y="28" text-anchor="middle" font-size="9" font-family="Georgia, serif" fill="#141413">{label}</text>
        <rect x="130" y="52" width="180" height="100" fill="#EAE4D7" stroke="#141413" stroke-width="1.2"/>
        <line x1="130" y1="165" x2="310" y2="165" stroke="#8c6d28" stroke-width="0.8"/>
        <line x1="115" y1="52" x2="115" y2="152" stroke="#8c6d28" stroke-width="0.8"/>
        <text x="220" y="178" text-anchor="middle" font-size="8" fill="#625E57">{html.escape(dims)}</text>
    </svg>
    """


def _infer_cad_defaults_from_dictamen(dictamen: str, saved_cad: dict) -> dict:
    """Detecta automáticamente en el texto del dictamen el estilo de anillo, engaste y corte para abrir el gráfico ya ajustado."""
    if saved_cad and saved_cad.get("shank_profile"):
        return saved_cad

    text = (dictamen or "").lower()
    defaults = dict(saved_cad or {})

    if any(w in text for w in ("pulsera", "brazalete", "esclava")):
        defaults.setdefault("jewelry_type", "Pulsera / Brazalete")
    elif any(w in text for w in ("collar", "colgante", "gargantilla", "cadena")):
        defaults.setdefault("jewelry_type", "Collar / Colgante")
    else:
        defaults.setdefault("jewelry_type", "Anillo / Sortija")

    # Inferir perfil de banda (Shank)
    if any(w in text for w in ("media alianza", "half eternity", "sinfín", "sinfin", "5 esmeraldas", "7 esmeraldas", "alternating")):
        defaults.setdefault("shank_profile", "Media Alianza (Piedras en arco superior)")
    elif any(w in text for w in ("alianza completa", "eternity", "todo el perímetro", "pavé continuo", "banda ancha abombada")):
        defaults.setdefault("shank_profile", "Eternity / Sin fin (Piedras en todo el perímetro)")
    elif "catedral" in text:
        defaults.setdefault("shank_profile", "Catedral (Hombros elevados hacia cabeza)")
    elif "split" in text or "bifurcad" in text or "hombros divididos" in text:
        defaults.setdefault("shank_profile", "Split Shank (Banda dividida en hombros)")
    elif "bypass" in text or "cruzad" in text or "toi et moi" in text:
        defaults.setdefault("shank_profile", "Bypass (Brazos cruzados envolventes)")
    elif "europeo" in text or "cuadrada" in text:
        defaults.setdefault("shank_profile", "Estilo Europeo (Base cuadrada anti-giro)")
    elif "tapered" in text or "afilad" in text or "adelgazamiento" in text:
        defaults.setdefault("shank_profile", "Tapered (Banda afilada hacia la piedra)")
    else:
        defaults.setdefault("shank_profile", "Tradicional (Aro redondo clásico)")

    # Inferir engaste (Setting)
    if any(w in text for w in ("pavé", "pave", "micro-pavé", "granos")):
        defaults.setdefault("setting_arch", "Pavé / Micro-pavé (Granos engastados en masa)")
    elif any(w in text for w in ("carril", "canal", "barra", "channel")):
        defaults.setdefault("setting_arch", "Barra / Carril / Canal (Channel setting)")
    elif "semi-bisel" in text or "semibisel" in text:
        defaults.setdefault("setting_arch", "Semi-Biselado (Bezel abierto lateral)")
    elif "bisel" in text or "chatón cerrado" in text or "bezel" in text:
        defaults.setdefault("setting_arch", "Biselado completo (Bezel cerrado)")
    elif "corona" in text or "calad" in text or "decorativ" in text:
        defaults.setdefault("setting_arch", "Decorativo / Corona calada")
    elif "espiga" in text or "v-prong" in text:
        defaults.setdefault("setting_arch", "Espiga / V-Prong (Garras en V abiertas)")
    else:
        defaults.setdefault("setting_arch", "Canasta (4 o 6 garras con galería abierta)")

    # Inferir corte de piedra principal
    if "baguette" in text or "carré" in text or "escalonada" in text:
        defaults.setdefault("central_cut", "Baguette / Carré (Escalonada)")
        defaults.setdefault("side_cut", "Brillante Redondo")
    elif "esmeralda" in text or "octogonal" in text or "rectangular" in text:
        defaults.setdefault("central_cut", "Esmeralda / Octogonal")
    elif "cabujón" in text or "cabujon" in text:
        defaults.setdefault("central_cut", "Cabujón (Liso abombado)")
    else:
        defaults.setdefault("central_cut", "Brillante Redondo")

    return defaults


def _gem_shape_svg(cx: float, cy: float, rx: float, ry: float, cut: str, show_prongs: bool = True) -> str:
    """Dibuja la geometría cenital exacta de la piedra según su talla (Brillante, Esmeralda, Baguette, Oval, Pera, Marquesa, Cabujón)."""
    cut_l = (cut or "").lower()
    parts = []
    if "esmeralda" in cut_l or "octogonal" in cut_l:
        c = min(rx, ry) * 0.35
        pts = f"{cx-rx+c},{cy-ry} {cx+rx-c},{cy-ry} {cx+rx},{cy-ry+c} {cx+rx},{cy+ry-c} {cx+rx-c},{cy+ry} {cx-rx+c},{cy+ry} {cx-rx},{cy+ry-c} {cx-rx},{cy-ry+c}"
        irx, iry, ic = rx * 0.65, ry * 0.65, c * 0.65
        ipts = f"{cx-irx+ic},{cy-iry} {cx+irx-ic},{cy-iry} {cx+irx},{cy-iry+ic} {cx+irx},{cy+iry-ic} {cx+irx-ic},{cy+iry} {cx-irx+ic},{cy+iry} {cx-irx},{cy+iry-ic} {cx-irx},{cy-iry+ic}"
        parts.append(f"<polygon points='{pts}' fill='#F3EFE6' stroke='#141413' stroke-width='1.5'/>")
        parts.append(f"<polygon points='{ipts}' fill='none' stroke='#141413' stroke-width='0.8'/>")
    elif "baguette" in cut_l or "carré" in cut_l or "princesa" in cut_l:
        parts.append(f"<rect x='{cx-rx}' y='{cy-ry}' width='{rx*2}' height='{ry*2}' fill='#F3EFE6' stroke='#141413' stroke-width='1.5'/>")
        parts.append(f"<rect x='{cx-rx*0.65}' y='{cy-ry*0.65}' width='{rx*1.3}' height='{ry*1.3}' fill='none' stroke='#141413' stroke-width='0.8'/>")
        parts.append(f"<line x1='{cx-rx}' y1='{cy-ry}' x2='{cx-rx*0.65}' y2='{cy-ry*0.65}' stroke='#141413' stroke-width='0.7'/>")
        parts.append(f"<line x1='{cx+rx}' y1='{cy-ry}' x2='{cx+rx*0.65}' y2='{cy-ry*0.65}' stroke='#141413' stroke-width='0.7'/>")
        parts.append(f"<line x1='{cx-rx}' y1='{cy+ry}' x2='{cx-rx*0.65}' y2='{cy+ry*0.65}' stroke='#141413' stroke-width='0.7'/>")
        parts.append(f"<line x1='{cx+rx}' y1='{cy+ry}' x2='{cx+rx*0.65}' y2='{cy+ry*0.65}' stroke='#141413' stroke-width='0.7'/>")
    elif "marquesa" in cut_l or "navette" in cut_l:
        parts.append(f"<path d='M {cx-rx*1.25} {cy} Q {cx} {cy-ry*1.3} {cx+rx*1.25} {cy} Q {cx} {cy+ry*1.3} {cx-rx*1.25} {cy} Z' fill='#F3EFE6' stroke='#141413' stroke-width='1.5'/>")
        parts.append(f"<ellipse cx='{cx}' cy='{cy}' rx='{rx*0.6}' ry='{ry*0.45}' fill='none' stroke='#141413' stroke-width='0.8'/>")
    elif "pera" in cut_l or "lágrima" in cut_l:
        parts.append(f"<path d='M {cx} {cy-ry*1.25} C {cx+rx*1.2} {cy-ry*0.2} {cx+rx*1.1} {cy+ry*1.1} {cx} {cy+ry*1.1} C {cx-rx*1.1} {cy+ry*1.1} {cx-rx*1.2} {cy-ry*0.2} {cx} {cy-ry*1.25} Z' fill='#F3EFE6' stroke='#141413' stroke-width='1.5'/>")
        parts.append(f"<circle cx='{cx}' cy='{cy+ry*0.2}' r='{min(rx,ry)*0.5}' fill='none' stroke='#141413' stroke-width='0.8'/>")
    elif "oval" in cut_l or "cojín" in cut_l:
        parts.append(f"<ellipse cx='{cx}' cy='{cy}' rx='{rx*1.1}' ry='{ry*0.85}' fill='#F3EFE6' stroke='#141413' stroke-width='1.5'/>")
        parts.append(f"<ellipse cx='{cx}' cy='{cy}' rx='{rx*0.68}' ry='{ry*0.52}' fill='none' stroke='#141413' stroke-width='0.8'/>")
    elif "cabujón" in cut_l:
        parts.append(f"<ellipse cx='{cx}' cy='{cy}' rx='{rx}' ry='{ry*0.88}' fill='#EAE4D7' stroke='#141413' stroke-width='1.6'/>")
        parts.append(f"<path d='M {cx-rx*0.6} {cy-ry*0.3} Q {cx} {cy-ry*0.75} {cx+rx*0.6} {cy-ry*0.3}' fill='none' stroke='#141413' stroke-width='0.9'/>")
    else:
        # Brillante Redondo / Talla Antigua
        r = min(rx, ry)
        parts.append(f"<circle cx='{cx}' cy='{cy}' r='{r}' fill='#F3EFE6' stroke='#141413' stroke-width='1.5'/>")
        parts.append(f"<polygon points='{cx},{cy-r*0.68} {cx+r*0.48},{cy-r*0.48} {cx+r*0.68},{cy} {cx+r*0.48},{cy+r*0.48} {cx},{cy+r*0.68} {cx-r*0.48},{cy+r*0.48} {cx-r*0.68},{cy} {cx-r*0.48},{cy-r*0.48}' fill='none' stroke='#141413' stroke-width='0.75'/>")

    if show_prongs:
        for px, py in ((cx - rx * 0.85, cy - ry * 0.85), (cx + rx * 0.85, cy - ry * 0.85), (cx - rx * 0.85, cy + ry * 0.85), (cx + rx * 0.85, cy + ry * 0.85)):
            parts.append(f"<circle cx='{px}' cy='{py}' r='2.1' fill='#141413'/>")
    return "".join(parts)


def _setting_macro_svg(setting_arch: str) -> str:
    """Dibuja en la columna derecha del plano (x=315..425) la arquitectura exacta del engaste seleccionado."""
    s_low = (setting_arch or "").lower()
    # Coordenadas base del zoom de engaste: centro x=370, y=92
    if "biselado completo" in s_low:
        return """
        <!-- Engaste Biselado Completo (Bezel cerrado envolvente) -->
        <polygon points="342,68 398,68 388,56 352,56" fill="#EAE4D7" stroke="#141413" stroke-width="1.3"/>
        <polygon points="334,70 406,70 398,118 342,118" fill="none" stroke="#141413" stroke-width="1.8"/>
        <line x1="336" y1="77" x2="404" y2="77" stroke="#141413" stroke-width="1.1"/>
        <text x="370" y="135" text-anchor="middle" font-size="8" font-family="Inter, sans-serif" font-weight="600" fill="#141413">BISELADO CERRADO</text>
        <text x="370" y="146" text-anchor="middle" font-size="7" font-family="Inter, sans-serif" fill="#625E57">Metal rodea toda la piedra</text>
        """
    if "semi-biselado" in s_low:
        return """
        <!-- Engaste Semi-Biselado (Abierto en dos frentes) -->
        <polygon points="344,64 396,64 386,53 354,53" fill="#F3EFE6" stroke="#141413" stroke-width="1.3"/>
        <path d="M 334,65 L 352,65 L 356,118 L 340,118 Z" fill="#EAE4D7" stroke="#141413" stroke-width="1.6"/>
        <path d="M 406,65 L 388,65 L 384,118 L 400,118 Z" fill="#EAE4D7" stroke="#141413" stroke-width="1.6"/>
        <polygon points="354,65 386,65 370,96" fill="none" stroke="#141413" stroke-width="0.9" stroke-dasharray="2,2"/>
        <text x="370" y="135" text-anchor="middle" font-size="8" font-family="Inter, sans-serif" font-weight="600" fill="#141413">SEMI-BISELADO</text>
        <text x="370" y="146" text-anchor="middle" font-size="7" font-family="Inter, sans-serif" fill="#625E57">Paredes laterales con centro libre</text>
        """
    if "barra" in s_low or "carril" in s_low or "canal" in s_low:
        return """
        <!-- Engaste Barra / Canal (Rieles continuos sin garras) -->
        <polygon points="335,68 405,68 400,116 340,116" fill="none" stroke="#141413" stroke-width="1.7"/>
        <line x1="335" y1="76" x2="405" y2="76" stroke="#141413" stroke-width="1.5"/>
        <rect x="344" y="60" width="16" height="16" fill="#F3EFE6" stroke="#141413" stroke-width="1.2"/>
        <rect x="362" y="60" width="16" height="16" fill="#F3EFE6" stroke="#141413" stroke-width="1.2"/>
        <rect x="380" y="60" width="16" height="16" fill="#F3EFE6" stroke="#141413" stroke-width="1.2"/>
        <text x="370" y="135" text-anchor="middle" font-size="8" font-family="Inter, sans-serif" font-weight="600" fill="#141413">BARRA / CANAL</text>
        <text x="370" y="146" text-anchor="middle" font-size="7" font-family="Inter, sans-serif" fill="#625E57">Piedras sujetas entre dos rieles</text>
        """
    if "pavé" in s_low or "pave" in s_low:
        return """
        <!-- Engaste Pavé / Micro-pavé -->
        <rect x="334" y="64" width="72" height="48" fill="#EAE4D7" stroke="#141413" stroke-width="1.5"/>
        <circle cx="348" cy="78" r="7" fill="#F3EFE6" stroke="#141413" stroke-width="1.1"/>
        <circle cx="370" cy="78" r="7" fill="#F3EFE6" stroke="#141413" stroke-width="1.1"/>
        <circle cx="392" cy="78" r="7" fill="#F3EFE6" stroke="#141413" stroke-width="1.1"/>
        <circle cx="359" cy="96" r="7" fill="#F3EFE6" stroke="#141413" stroke-width="1.1"/>
        <circle cx="381" cy="96" r="7" fill="#F3EFE6" stroke="#141413" stroke-width="1.1"/>
        <circle cx="359" cy="78" r="1.5" fill="#141413"/><circle cx="381" cy="78" r="1.5" fill="#141413"/>
        <circle cx="348" cy="96" r="1.5" fill="#141413"/><circle cx="370" cy="96" r="1.5" fill="#141413"/><circle cx="392" cy="96" r="1.5" fill="#141413"/>
        <text x="370" y="135" text-anchor="middle" font-size="8" font-family="Inter, sans-serif" font-weight="600" fill="#141413">PAVÉ / MICRO-PAVÉ</text>
        <text x="370" y="146" text-anchor="middle" font-size="7" font-family="Inter, sans-serif" fill="#625E57">Manto continuo con micro-granos</text>
        """
    if "espiga" in s_low or "v-prong" in s_low:
        return """
        <!-- Engaste en Espiga (Garras en V convergentes) -->
        <polygon points="340,64 400,64 388,52 352,52" fill="#F3EFE6" stroke="#141413" stroke-width="1.3"/>
        <polygon points="342,64 398,64 370,104" fill="none" stroke="#141413" stroke-width="1"/>
        <line x1="338" y1="58" x2="367" y2="120" stroke="#141413" stroke-width="2.4"/>
        <line x1="402" y1="58" x2="373" y2="120" stroke="#141413" stroke-width="2.4"/>
        <line x1="370" y1="58" x2="370" y2="120" stroke="#141413" stroke-width="2"/>
        <text x="370" y="135" text-anchor="middle" font-size="8" font-family="Inter, sans-serif" font-weight="600" fill="#141413">ESPIGA (EN V)</text>
        <text x="370" y="146" text-anchor="middle" font-size="7" font-family="Inter, sans-serif" fill="#625E57">Garras en V desde un vértice</text>
        """
    if "decorativo" in s_low or "corona" in s_low:
        return """
        <!-- Engaste Decorativo / Corona Calada -->
        <polygon points="340,64 400,64 388,52 352,52" fill="#F3EFE6" stroke="#141413" stroke-width="1.3"/>
        <path d="M 338,62 L 348,114 L 392,114 L 402,62" fill="none" stroke="#141413" stroke-width="1.6"/>
        <path d="M 343,88 Q 356,66 370,88 Q 384,66 397,88" fill="none" stroke="#141413" stroke-width="1.3"/>
        <path d="M 346,104 Q 370,76 394,104" fill="none" stroke="#141413" stroke-width="1.1"/>
        <text x="370" y="135" text-anchor="middle" font-size="8" font-family="Inter, sans-serif" font-weight="600" fill="#141413">CORONA DECORATIVA</text>
        <text x="370" y="146" text-anchor="middle" font-size="7" font-family="Inter, sans-serif" fill="#625E57">Cesto calado con volutas/arcos</text>
        """
    # Por defecto: Canasta clásica (4 o 6 garras con galería horizontal)
    return """
    <!-- Engaste en Canasta (Garras verticales + galería horizontal) -->
    <polygon points="340,64 400,64 388,52 352,52" fill="#F3EFE6" stroke="#141413" stroke-width="1.3"/>
    <polygon points="342,64 398,64 370,104" fill="none" stroke="#141413" stroke-width="0.9" stroke-dasharray="2,2"/>
    <line x1="340" y1="56" x2="346" y2="116" stroke="#141413" stroke-width="2.3"/>
    <line x1="358" y1="56" x2="360" y2="116" stroke="#141413" stroke-width="2"/>
    <line x1="382" y1="56" x2="380" y2="116" stroke="#141413" stroke-width="2"/>
    <line x1="400" y1="56" x2="394" y2="116" stroke="#141413" stroke-width="2.3"/>
    <line x1="342" y1="82" x2="398" y2="82" stroke="#141413" stroke-width="1.6"/>
    <line x1="346" y1="114" x2="394" y2="114" stroke="#141413" stroke-width="1.6"/>
    <text x="370" y="135" text-anchor="middle" font-size="8" font-family="Inter, sans-serif" font-weight="600" fill="#141413">CANASTA CLÁSICA</text>
    <text x="370" y="146" text-anchor="middle" font-size="7" font-family="Inter, sans-serif" fill="#625E57">Garras con galería horizontal</text>
    """


def _dynamic_blueprint_svg_html(
    jewelry_type: str,
    shank_profile: str,
    setting_arch: str,
    central_cut: str = "Brillante Redondo",
    side_cut: str = "Brillante Redondo",
    side_count: int = 0,
) -> str:
    """
    Renderiza en vivo el Plano Técnico CAD adaptando:
    - Vista I (Izquierda): Alzado / Perfil del aro según Shank (Tradicional, Europeo, Catedral, Media Alianza, Eternity)
    - Vista II (Centro): Planta Cenital de la banda (Straight, Tapered, Reverse Tapered, Split, Bypass) + Talla real de las piedras
    - Vista III (Derecha): Zoom macro del Engaste seleccionado (Canasta, Espiga, Decorativo, Biselado, Semi-Biselado, Barra/Canal, Pavé)
    """
    if jewelry_type == "Pulsera / Brazalete":
        setting_svg = _setting_macro_svg(setting_arch)
        return f"""
        <div class="blueprint-box">
            <div class="flex justify-between items-center mb-1">
                <span class="micro-coord text-[#141413]">PLANO REACTIVO CAD // PULSERA &amp; ENGASTE</span>
                <span class="micro-coord">{html.escape(setting_arch.split('(')[0].strip())}</span>
            </div>
            <svg viewBox="0 0 435 160" class="w-full h-40">
                <text x="110" y="20" text-anchor="middle" font-size="7.5" font-family="Inter, sans-serif" fill="#625E57">I. PERFIL DE MUÑECA</text>
                <ellipse cx="110" cy="85" rx="75" ry="46" fill="none" stroke="#141413" stroke-width="1.6"/>
                <ellipse cx="110" cy="85" rx="64" ry="37" fill="none" stroke="#141413" stroke-width="1"/>
                <line x1="46" y1="85" x2="174" y2="85" stroke="#141413" stroke-width="0.9" stroke-dasharray="3,2"/>
                <text x="110" y="80" text-anchor="middle" font-size="8" font-family="Inter, sans-serif" fill="#141413">A: Ø INT / LARGO</text>
                <text x="110" y="146" text-anchor="middle" font-size="7.5" font-family="Inter, sans-serif" fill="#141413">B: ANCHO ESLABÓN · C: ESPESOR</text>
                <line x1="295" y1="15" x2="295" y2="150" stroke="#B8B2A4" stroke-width="0.8" stroke-dasharray="2,2"/>
                <text x="370" y="20" text-anchor="middle" font-size="7.5" font-family="Inter, sans-serif" fill="#625E57">II. DETALLE DE ENGASTE</text>
                {setting_svg}
            </svg>
        </div>
        """

    if jewelry_type == "Collar / Colgante":
        setting_svg = _setting_macro_svg(setting_arch)
        gem_svg = _gem_shape_svg(135, 102, 18, 22, central_cut, show_prongs=False)
        return f"""
        <div class="blueprint-box">
            <div class="flex justify-between items-center mb-1">
                <span class="micro-coord text-[#141413]">PLANO REACTIVO CAD // COLLAR, TALLA &amp; ENGASTE</span>
                <span class="micro-coord">{html.escape(central_cut)}</span>
            </div>
            <svg viewBox="0 0 435 160" class="w-full h-40">
                <text x="135" y="18" text-anchor="middle" font-size="7.5" font-family="Inter, sans-serif" fill="#625E57">I. CAÍDA Y MOTIVO CENTRAL</text>
                <path d="M 55 26 Q 135 95 215 26" fill="none" stroke="#141413" stroke-width="1.4" stroke-dasharray="4,2"/>
                <circle cx="135" cy="68" r="5" fill="none" stroke="#141413" stroke-width="1.3"/>
                {gem_svg}
                <text x="135" y="145" text-anchor="middle" font-size="8" font-family="Inter, sans-serif" fill="#141413">A: LARGO CADENA · E: GEMA ({html.escape(central_cut.split('/')[0].strip())})</text>
                <line x1="295" y1="15" x2="295" y2="150" stroke="#B8B2A4" stroke-width="0.8" stroke-dasharray="2,2"/>
                <text x="370" y="18" text-anchor="middle" font-size="7.5" font-family="Inter, sans-serif" fill="#625E57">II. DETALLE DE ENGASTE</text>
                {setting_svg}
            </svg>
        </div>
        """

    # =========================================================================
    # PLANO REACTIVO DE ANILLO / SORTIJA (3 VISTAS DINÁMICAS: PERFIL + PLANTA + ENGASTE)
    # =========================================================================
    s_prof = (shank_profile or "").lower()
    is_half_eternity = "media alianza" in s_prof
    is_full_eternity = "eternity" in s_prof or "sin fin" in s_prof

    # --- VISTA I: PERFIL DEL ARO (x=15..135, centro cx=72, cy=94) ---
    if is_full_eternity:
        profile_svg = """
        <circle cx="72" cy="92" r="40" fill="none" stroke="#141413" stroke-width="1.6"/>
        <circle cx="72" cy="92" r="31" fill="none" stroke="#141413" stroke-width="1.1"/>
        <!-- Piedras en todo el perímetro -->
        <circle cx="72" cy="48" r="4" fill="#F3EFE6" stroke="#141413" stroke-width="1.1"/>
        <circle cx="94" cy="54" r="4" fill="#F3EFE6" stroke="#141413" stroke-width="1.1"/>
        <circle cx="110" cy="70" r="4" fill="#F3EFE6" stroke="#141413" stroke-width="1.1"/>
        <circle cx="116" cy="92" r="4" fill="#F3EFE6" stroke="#141413" stroke-width="1.1"/>
        <circle cx="110" cy="114" r="4" fill="#F3EFE6" stroke="#141413" stroke-width="1.1"/>
        <circle cx="94" cy="130" r="4" fill="#F3EFE6" stroke="#141413" stroke-width="1.1"/>
        <circle cx="72" cy="136" r="4" fill="#F3EFE6" stroke="#141413" stroke-width="1.1"/>
        <circle cx="50" cy="130" r="4" fill="#F3EFE6" stroke="#141413" stroke-width="1.1"/>
        <circle cx="34" cy="114" r="4" fill="#F3EFE6" stroke="#141413" stroke-width="1.1"/>
        <circle cx="28" cy="92" r="4" fill="#F3EFE6" stroke="#141413" stroke-width="1.1"/>
        <circle cx="34" cy="70" r="4" fill="#F3EFE6" stroke="#141413" stroke-width="1.1"/>
        <circle cx="50" cy="54" r="4" fill="#F3EFE6" stroke="#141413" stroke-width="1.1"/>
        """
    elif is_half_eternity:
        profile_svg = """
        <circle cx="72" cy="94" r="40" fill="none" stroke="#141413" stroke-width="1.5"/>
        <circle cx="72" cy="94" r="32" fill="none" stroke="#141413" stroke-width="1"/>
        <!-- Arco superior engastado (Media Alianza) -->
        <rect x="67" y="49" width="10" height="7" fill="#F3EFE6" stroke="#141413" stroke-width="1.2"/>
        <rect x="53" y="52" width="10" height="7" transform="rotate(-18 58 55)" fill="#F3EFE6" stroke="#141413" stroke-width="1.2"/>
        <rect x="81" y="52" width="10" height="7" transform="rotate(18 86 55)" fill="#F3EFE6" stroke="#141413" stroke-width="1.2"/>
        <rect x="40" y="60" width="9" height="7" transform="rotate(-36 44 63)" fill="#F3EFE6" stroke="#141413" stroke-width="1.2"/>
        <rect x="95" y="60" width="9" height="7" transform="rotate(36 99 63)" fill="#F3EFE6" stroke="#141413" stroke-width="1.2"/>
        """
    elif "europeo" in s_prof:
        profile_svg = """
        <!-- Aro Estilo Europeo (Base cuadrada anti-giro) -->
        <path d="M 32,94 A 40,40 0 1,1 112,94 L 106,133 Q 72,138 38,133 Z" fill="none" stroke="#141413" stroke-width="1.6"/>
        <circle cx="72" cy="94" r="31" fill="none" stroke="#141413" stroke-width="1"/>
        <polygon points="58,40 86,40 81,54 63,54" fill="#F3EFE6" stroke="#141413" stroke-width="1.4"/>
        """
    elif "catedral" in s_prof:
        profile_svg = """
        <!-- Aro Catedral (Hombros arqueados elevados hasta la cabeza) -->
        <circle cx="72" cy="96" r="39" fill="none" stroke="#141413" stroke-width="1.5"/>
        <circle cx="72" cy="96" r="31" fill="none" stroke="#141413" stroke-width="1"/>
        <path d="M 35,82 Q 44,44 61,46" fill="none" stroke="#141413" stroke-width="1.8"/>
        <path d="M 109,82 Q 100,44 83,46" fill="none" stroke="#141413" stroke-width="1.8"/>
        <polygon points="58,36 86,36 81,56 63,56" fill="#F3EFE6" stroke="#141413" stroke-width="1.5"/>
        """
    else:
        profile_svg = """
        <!-- Aro Tradicional Redondo -->
        <circle cx="72" cy="96" r="39" fill="none" stroke="#141413" stroke-width="1.5"/>
        <circle cx="72" cy="96" r="31" fill="none" stroke="#141413" stroke-width="1"/>
        <polygon points="58,40 86,40 81,57 63,57" fill="#F3EFE6" stroke="#141413" stroke-width="1.4"/>
        """

    # --- VISTA II: PLANTA CENITAL DE LA BANDA Y PIEDRAS (x=145..295, centro cx=220, cy=88) ---
    if is_half_eternity or is_full_eternity:
        # Fila continua de gemas (ej. 5 o 7 piedras alternadas)
        n_stones = max(min(int(side_count or 7), 9), 5)
        stone_w = 110.0 / n_stones
        stones_svg = []
        start_x = 220 - (n_stones * stone_w) / 2.0 + stone_w / 2.0
        for i in range(n_stones):
            sx = start_x + i * stone_w
            active_cut = side_cut if (i % 2 == 1 and side_cut != central_cut) else central_cut
            stones_svg.append(_gem_shape_svg(sx, 88, stone_w * 0.44, 10, active_cut, show_prongs=False))
        shank_top_svg = f"""
        <rect x="152" y="76" width="136" height="24" fill="#EAE4D7" stroke="#141413" stroke-width="1.5"/>
        <line x1="152" y1="79" x2="288" y2="79" stroke="#141413" stroke-width="1"/>
        <line x1="152" y1="97" x2="288" y2="97" stroke="#141413" stroke-width="1"/>
        {''.join(stones_svg)}
        <text x="220" y="64" text-anchor="middle" font-size="7.8" font-family="Inter, sans-serif" fill="#141413">F: FILA DE {n_stones} PIEDRAS EN BANDA</text>
        """
    else:
        if "reverse tapered" in s_prof:
            band_path = "<polygon points='152,82 202,73 202,103 152,94' fill='#EAE4D7' stroke='#141413' stroke-width='1.4'/><polygon points='288,82 238,73 238,103 288,94' fill='#EAE4D7' stroke='#141413' stroke-width='1.4'/>"
        elif "tapered" in s_prof:
            band_path = "<polygon points='152,74 204,83 204,93 152,102' fill='#EAE4D7' stroke='#141413' stroke-width='1.4'/><polygon points='288,74 236,83 236,93 288,102' fill='#EAE4D7' stroke='#141413' stroke-width='1.4'/>"
        elif "split" in s_prof:
            band_path = """
            <path d='M 152,80 L 178,80 L 204,70 L 204,78 L 182,88 L 204,98 L 204,106 L 178,96 L 152,96 Z' fill='#EAE4D7' stroke='#141413' stroke-width='1.3'/>
            <path d='M 288,80 L 262,80 L 236,70 L 236,78 L 258,88 L 236,98 L 236,106 L 262,96 L 288,96 Z' fill='#EAE4D7' stroke='#141413' stroke-width='1.3'/>
            """
        elif "bypass" in s_prof:
            band_path = """
            <path d='M 152,98 Q 185,98 214,68 L 222,75 Q 190,108 152,108 Z' fill='#EAE4D7' stroke='#141413' stroke-width='1.3'/>
            <path d='M 288,78 Q 255,78 226,108 L 218,101 Q 250,68 288,68 Z' fill='#EAE4D7' stroke='#141413' stroke-width='1.3'/>
            """
        else:
            # Straight / Tradicional / Catedral / Europeo
            band_path = "<rect x='152' y='78' width='136' height='20' fill='#EAE4D7' stroke='#141413' stroke-width='1.4'/>"

        center_gem = _gem_shape_svg(220, 88, 17, 17, central_cut, show_prongs=("bisel" not in setting_arch.lower()))
        side_gems = ""
        if int(side_count or 0) > 0:
            side_gems = (
                _gem_shape_svg(192, 88, 6.5, 6.5, side_cut, show_prongs=False)
                + _gem_shape_svg(177, 88, 5.5, 5.5, side_cut, show_prongs=False)
                + _gem_shape_svg(248, 88, 6.5, 6.5, side_cut, show_prongs=False)
                + _gem_shape_svg(263, 88, 5.5, 5.5, side_cut, show_prongs=False)
            )
        shank_top_svg = f"""
        {band_path}
        {side_gems}
        {center_gem}
        <text x="220" y="61" text-anchor="middle" font-size="7.8" font-family="Inter, sans-serif" fill="#141413">E: CENTRAL ({html.escape(central_cut.split('/')[0].strip().upper())})</text>
        """

    setting_svg = _setting_macro_svg(setting_arch)

    return f"""
    <div class="blueprint-box">
        <div class="flex justify-between items-center mb-1 border-b border-[#B8B2A4] pb-1">
            <span class="micro-coord text-[#141413]">PLANO TÉCNICO INTERACTIVO // CAMBIA SEGÚN ESTILO Y ENGASTE</span>
            <span class="micro-coord text-[#8c6d28]">{html.escape(shank_profile.split('(')[0].strip())} · {html.escape(setting_arch.split('(')[0].strip())}</span>
        </div>
        <svg viewBox="0 0 435 162" class="w-full h-44">
            <!-- Encabezados de las 3 vistas -->
            <text x="72" y="16" text-anchor="middle" font-size="7.2" font-family="Inter, sans-serif" font-weight="600" fill="#625E57">I. PERFIL DE ARO</text>
            <text x="220" y="16" text-anchor="middle" font-size="7.2" font-family="Inter, sans-serif" font-weight="600" fill="#625E57">II. PLANTA DE BANDA Y TALLA</text>
            <text x="370" y="16" text-anchor="middle" font-size="7.2" font-family="Inter, sans-serif" font-weight="600" fill="#625E57">III. ARQUITECTURA ENGASTE</text>

            <!-- Separadores verticales -->
            <line x1="140" y1="10" x2="140" y2="152" stroke="#B8B2A4" stroke-width="0.8" stroke-dasharray="2,2"/>
            <line x1="302" y1="10" x2="302" y2="152" stroke="#B8B2A4" stroke-width="0.8" stroke-dasharray="2,2"/>

            <!-- Vista I: Perfil -->
            {profile_svg}
            <line x1="41" y1="96" x2="103" y2="96" stroke="#141413" stroke-width="0.8" stroke-dasharray="2,2"/>
            <text x="72" y="92" text-anchor="middle" font-size="7.5" font-family="Inter, sans-serif" fill="#141413">A: Ø INT</text>
            <text x="72" y="150" text-anchor="middle" font-size="7.2" font-family="Inter, sans-serif" fill="#141413">C: ESPESOR ARO</text>

            <!-- Vista II: Planta Cenital -->
            {shank_top_svg}
            <text x="220" y="125" text-anchor="middle" font-size="7.5" font-family="Inter, sans-serif" fill="#141413">B: ANCHO DE BANDA (MM)</text>
            <text x="220" y="148" text-anchor="middle" font-size="7.2" font-family="Inter, sans-serif" fill="#625E57">{html.escape(shank_profile.split('(')[0].strip().upper())}</text>

            <!-- Vista III: Zoom Macro del Engaste -->
            {setting_svg}
        </svg>
    </div>
    """


def _plain_language_measurement_guide(shank_profile: str, setting_arch: str) -> str:
    """Devuelve una guía en lenguaje llano para que cualquier usuario no experto sepa qué medir viendo el dibujo."""
    s_prof = (shank_profile or "").lower()
    s_set = (setting_arch or "").lower()

    if "media alianza" in s_prof or "eternity" in s_prof:
        ring_tip = (
            "Es un anillo de fila de piedras (sin solitario central aislado). "
            "Cuenta cuántas piedras hay en la fila (ej. 5 esmeraldas y 4 diamantes, o 7 y 5) y anota el ancho de una piedra en mm en el bloque de 'Piedras en Banda / Alianza'."
        )
    elif "split" in s_prof:
        ring_tip = "La banda se divide en dos brazos al llegar a la piedra central. Mide el ancho de la banda abajo (Cota B) y el largo × ancho de la piedra central (Cota E)."
    elif "catedral" in s_prof:
        ring_tip = "Los hombros suben formando arcos laterales que sostienen la piedra en alto. Mide la altura desde el dedo hasta la cima de la piedra (Cota D)."
    else:
        ring_tip = "Mide con una regla milimetrada el hueco interior del anillo de lado a lado (Cota A: Ø Int) y el grosor de la banda (Cota B)."

    if "barra" in s_set or "canal" in s_set:
        set_tip = "Engaste en Canal: las piedras van encajadas dentro de dos rieles continuos de metal, sin patillas individuales."
    elif "bisel" in s_set:
        set_tip = "Engaste Biselado: un borde o collarín de metal abraza el contorno de la piedra protegiendo sus bordes."
    elif "pavé" in s_set:
        set_tip = "Engaste Pavé: la superficie está tapizada de pequeñas piedras juntas sujetas por diminutos granos de metal."
    else:
        set_tip = "Engaste de Garras / Canasta: pequeñas patillas metálicas suben desde la base para abrazar la piedra dejando entrar la luz por debajo."

    return f"{ring_tip} · {set_tip}"
