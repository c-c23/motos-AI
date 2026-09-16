"""
styles/theme.py
---------------
Sistema visual centralizado para Motos AI Leads.
Define tokens de diseño, CSS global y funciones de badge reutilizables.

ALCANCE: SOLO presentación visual. Sin lógica de negocio.
"""

from __future__ import annotations

# ──────────────────────────────────────────────
# TOKENS DE COLOR
# ──────────────────────────────────────────────
COLORS: dict[str, str] = {
    # Identidad
    "primary":       "#1B4F72",
    "primary_light": "#2E86DE",
    "bg_app":        "#F4F6F9",
    "bg_card":       "#FFFFFF",
    "border":        "#E2E8F0",

    # Texto
    "text_main":     "#1A1D23",
    "text_muted":    "#6B7280",
    "text_light":    "#9CA3AF",

    # Temperatura Crítico
    "critico_bg":    "#FDECEA",
    "critico_fg":    "#C0392B",
    "critico_dot":   "#E74C3C",

    # Temperatura Alto
    "alto_bg":       "#FEF0E6",
    "alto_fg":       "#D35400",
    "alto_dot":      "#E67E22",

    # Temperatura Medio
    "medio_bg":      "#FEF9E7",
    "medio_fg":      "#9A7D0A",
    "medio_dot":     "#F1C40F",

    # Temperatura Bajo
    "bajo_bg":       "#E9F7EF",
    "bajo_fg":       "#117A65",
    "bajo_dot":      "#27AE60",

    # Sin score
    "noscore_bg":    "#F4F6F9",
    "noscore_fg":    "#95A5A6",

    # Asignación
    "asignado_bg":   "#EBF5FB",
    "asignado_fg":   "#1F618D",
    "sinasig_bg":    "#FDF2E9",
    "sinasig_fg":    "#784212",

    # Estados operativos
    "success_bg":    "#E9F7EF",
    "success_fg":    "#1E8449",
    "warning_bg":    "#FEF9E7",
    "warning_fg":    "#9A7D0A",
    "error_bg":      "#FDECEA",
    "error_fg":      "#C0392B",

    # IA badge
    "ia_bg":         "#EEF2FF",
    "ia_fg":         "#4338CA",
}

# Colores semánticos por temperatura para gráficos Altair
TEMP_COLOR_SCALE = {
    "Crítico":   COLORS["critico_dot"],
    "Alto":      COLORS["alto_dot"],
    "Medio":     COLORS["medio_dot"],
    "Bajo":      COLORS["bajo_dot"],
    "Sin score": COLORS["noscore_fg"],
}

# ──────────────────────────────────────────────
# CSS GLOBAL
# ──────────────────────────────────────────────
def get_global_css() -> str:
    """
    Retorna el bloque CSS global que se inyecta en cada página via st.markdown.
    Aplica sobre el tema por defecto de Streamlit sin romper sus componentes.
    """
    c = COLORS
    return f"""
<style>
/* ── Tipografía base ── */
html, body, [class*="css"] {{
    font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
}}

/* ── Fondo de la aplicación ── */
.stApp {{
    background-color: {c['bg_app']};
}}

/* ── Sidebar ── */
[data-testid="stSidebar"] {{
    position: relative;
    background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
    border-right: 1px solid #334155;
}}
[data-testid="stSidebar"] > div:first-child {{
    background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
}}
[data-testid="stSidebar"] [data-testid="stSidebarNav"] {{
    padding: 1.15rem .8rem 5.5rem;
}}
[data-testid="stSidebar"] [data-testid="stSidebarNav"]::before {{
    content: "🏍️  Motos AI Leads\A CRM INTELLIGENCE";
    white-space: pre-line;
    display: block;
    padding: .15rem .55rem 1.15rem;
    margin: 0 .15rem 1rem;
    border-bottom: 1px solid #334155;
    color: #F8FAFC;
    font-size: .98rem;
    font-weight: 700;
    line-height: 1.65;
}}
[data-testid="stSidebar"] [data-testid="stSidebarNav"]::after {{
    content: none;
}}
[data-testid="stSidebar"]::after {{
    content: "Estado del sistema\A●  PostgreSQL activo";
    white-space: pre-line;
    position: absolute;
    right: 1rem;
    bottom: 1.1rem;
    left: 1rem;
    box-sizing: border-box;
    padding: .7rem .75rem;
    border: 1px solid #334155;
    border-radius: 8px;
    background: #1E293B;
    color: #BBF7D0;
    font-size: .72rem;
    font-weight: 600;
    line-height: 1.7;
}}
[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul {{
    gap: .2rem;
}}
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] {{
    min-height: 2.55rem;
    border-radius: 8px;
    color: #E0F2FE !important;
    font-size: .86rem;
    font-weight: 500;
}}
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] span {{
    color: inherit !important;
}}
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover {{
    background: #334155;
    color: #FFFFFF !important;
}}
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-selected="true"],
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] {{
    background: #0C4A6E;
    border-left: 3px solid #38BDF8;
    border-radius: 4px 8px 8px 4px;
    color: #FFFFFF !important;
    font-weight: 700;
}}
[data-testid="stSidebar"] button {{
    color: #CBD5E1 !important;
}}
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] label {{
    color: #DBEAFE !important;
}}
[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3 {{
    color: #BFDBFE !important;
}}
[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3 {{
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: {c['text_muted']};
    margin-top: 1rem;
    margin-bottom: 0.25rem;
}}

/* ── Métricas KPI ── */
[data-testid="stMetric"] {{
    background-color: {c['bg_card']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    padding: 16px 20px;
}}
[data-testid="stMetricLabel"] {{
    font-size: 0.7rem !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: {c['text_muted']} !important;
}}
[data-testid="stMetricValue"] {{
    font-size: 1.75rem !important;
    font-weight: 700 !important;
    color: {c['text_main']} !important;
}}

/* ── Tablas de datos ── */
[data-testid="stDataFrame"] {{
    border: 1px solid {c['border']};
    border-radius: 8px;
    overflow: hidden;
}}

/* ── Títulos ── */
h1 {{
    font-size: 1.5rem !important;
    font-weight: 700 !important;
    color: {c['text_main']} !important;
    margin-bottom: 0.15rem !important;
}}
h2 {{
    font-size: 1.1rem !important;
    font-weight: 600 !important;
    color: {c['text_main']} !important;
}}
h3 {{
    font-size: 0.85rem !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: {c['text_muted']} !important;
}}

/* ── Expanders ── */
[data-testid="stExpander"] {{
    border: 1px solid {c['border']} !important;
    border-radius: 8px !important;
    background-color: {c['bg_card']} !important;
    margin-bottom: 8px !important;
}}

/* ── Botones primarios ── */
[data-testid="stButton"] > button[kind="primary"] {{
    background-color: {c['primary_light']} !important;
    border-color: {c['primary_light']} !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
}}

/* ── Info/Warning/Error boxes ── */
[data-testid="stAlert"] {{
    border-radius: 8px !important;
}}

/* ── Caption ── */
[data-testid="stCaptionContainer"] p,
.stCaption {{
    color: {c['text_light']} !important;
    font-size: 0.75rem !important;
}}

/* ── Divider ── */
hr {{
    border-color: {c['border']} !important;
    margin: 1rem 0 !important;
}}

/* ── Tabs ── */
[data-testid="stTabs"] [role="tablist"] {{
    border-bottom: 2px solid {c['border']};
}}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{
    border-bottom-color: {c['primary_light']} !important;
    color: {c['primary_light']} !important;
    font-weight: 600 !important;
}}

/* ── Chat messages ── */
[data-testid="stChatMessage"] {{
    border-radius: 8px !important;
}}

/* ── Page links (quick access) ── */
[data-testid="stPageLink"] {{
    background-color: {c['bg_card']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    padding: 12px 16px;
    display: block;
    transition: border-color 0.15s;
}}
[data-testid="stPageLink"]:hover {{
    border-color: {c['primary_light']};
}}
</style>
"""


# ──────────────────────────────────────────────
# HELPERS DE BADGE HTML
# ──────────────────────────────────────────────
def _badge(text: str, bg: str, fg: str, dot: str | None = None) -> str:
    """Genera un badge HTML inline con colores explícitos."""
    dot_html = (
        f'<span style="display:inline-block;width:7px;height:7px;'
        f'border-radius:50%;background:{dot};margin-right:5px;'
        f'vertical-align:middle;"></span>'
        if dot else ""
    )
    return (
        f'<span style="display:inline-flex;align-items:center;'
        f'background:{bg};color:{fg};'
        f'font-size:0.72rem;font-weight:600;'
        f'padding:2px 9px;border-radius:4px;'
        f'white-space:nowrap;line-height:1.6;">'
        f"{dot_html}{text}</span>"
    )


def badge_temperatura(temperatura: str | None) -> str:
    """Badge HTML coloreado según temperatura del lead."""
    c = COLORS
    mapa = {
        "Crítico": ("Crítico", c["critico_bg"], c["critico_fg"], c["critico_dot"]),
        "Alto":    ("Alto",    c["alto_bg"],    c["alto_fg"],    c["alto_dot"]),
        "Medio":   ("Medio",   c["medio_bg"],   c["medio_fg"],   c["medio_dot"]),
        "Bajo":    ("Bajo",    c["bajo_bg"],    c["bajo_fg"],    c["bajo_dot"]),
        # compatibilidad con valores anteriores del sistema
        "Caliente": ("Crítico", c["critico_bg"], c["critico_fg"], c["critico_dot"]),
        "Tibio":    ("Medio",   c["medio_bg"],   c["medio_fg"],   c["medio_dot"]),
        "Frio":     ("Bajo",    c["bajo_bg"],    c["bajo_fg"],    c["bajo_dot"]),
        "Frío":     ("Bajo",    c["bajo_bg"],    c["bajo_fg"],    c["bajo_dot"]),
    }
    if temperatura in mapa:
        text, bg, fg, dot = mapa[temperatura]
        return _badge(text, bg, fg, dot)
    return _badge("Sin score", c["noscore_bg"], c["noscore_fg"])


def badge_asignacion(estado: str | None) -> str:
    """Badge HTML de estado de asignación."""
    c = COLORS
    if estado and str(estado).upper() == "ASIGNADO":
        return _badge("✓ Asignado", c["asignado_bg"], c["asignado_fg"])
    return _badge("○ Sin asignar", c["sinasig_bg"], c["sinasig_fg"])


def badge_ia() -> str:
    """Badge HTML identificador de extracción IA."""
    return _badge("IA", COLORS["ia_bg"], COLORS["ia_fg"])


def kpi_card_html(
    value: str,
    label: str,
    bg: str = "#FFFFFF",
    fg_value: str = "#1A1D23",
    fg_label: str = "#6B7280",
    border_color: str = "#E2E8F0",
    border_left: str | None = None,
) -> str:
    """
    Genera una tarjeta KPI como HTML para usar con st.markdown.
    Permite definir color de borde izquierdo para KPIs de temperatura.
    """
    border_left_css = (
        f"border-left: 4px solid {border_left};"
        if border_left
        else ""
    )
    return f"""
<div style="
    background:{bg};
    border:1px solid {border_color};
    {border_left_css}
    border-radius:8px;
    padding:16px 20px;
    margin-bottom:4px;
">
    <div style="font-size:0.68rem;font-weight:600;text-transform:uppercase;
                letter-spacing:0.05em;color:{fg_label};margin-bottom:6px;">
        {label}
    </div>
    <div style="font-size:1.9rem;font-weight:700;color:{fg_value};
                line-height:1.1;">
        {value}
    </div>
</div>
"""


def section_header_html(title: str, subtitle: str = "") -> str:
    """Cabecera de sección con estilo consistente."""
    sub = (
        f'<div style="font-size:0.75rem;color:#6B7280;margin-top:2px;">{subtitle}</div>'
        if subtitle else ""
    )
    return f"""
<div style="margin: 1.5rem 0 0.75rem 0;">
    <div style="font-size:0.72rem;font-weight:600;text-transform:uppercase;
                letter-spacing:0.07em;color:#6B7280;border-bottom:2px solid #E2E8F0;
                padding-bottom:6px;">
        {title}
    </div>
    {sub}
</div>
"""


def info_field_html(label: str, value: str) -> str:
    """Campo de información etiquetado para fichas de detalle."""
    val_style = "color:#9CA3AF;" if value in ("—", "", None, "null") else "color:#1A1D23;"
    return f"""
<div style="margin-bottom:10px;">
    <div style="font-size:0.68rem;font-weight:600;text-transform:uppercase;
                letter-spacing:0.05em;color:#9CA3AF;margin-bottom:2px;">
        {label}
    </div>
    <div style="font-size:0.875rem;font-weight:500;{val_style}">
        {value if value not in (None, "") else "—"}
    </div>
</div>
"""
