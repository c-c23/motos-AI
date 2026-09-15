"""Dashboard operacional: agregados de PostgreSQL, sin lógica de negocio."""

import altair as alt
import pandas as pd
import streamlit as st

from database import get_connection
from queries.dashboard_queries import (
    get_distribucion_prioridad, get_kpis, get_leads_asignados_vs_no,
    get_leads_por_empresa, get_leads_por_estado_gestion, get_leads_por_punto_venta,
    get_leads_por_temperatura,
)
from queries.leads_queries import get_valores_filtros
from styles.theme import (
    COLORS, TEMP_COLOR_SCALE, badge_temperatura,
    get_global_css, section_header_html,
)

st.set_page_config(page_title="Dashboard — Motos AI Leads", page_icon="📊", layout="wide")
st.markdown(get_global_css(), unsafe_allow_html=True)

# ── Encabezado ──────────────────────────────────────────────────────────────
st.markdown(
    f"<h1 style='margin-bottom:2px;'>Dashboard operativo</h1>"
    f"<div style='font-size:0.82rem;color:{COLORS['text_muted']};margin-bottom:1.5rem;'>"
    f"Indicadores agregados en tiempo real desde PostgreSQL</div>",
    unsafe_allow_html=True,
)


# ── Carga de datos ───────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def cargar_datos(empresa_id):
    with get_connection() as conn:
        return {
            'kpis': get_kpis(conn, empresa_id),
            'empresa': get_leads_por_empresa(conn, empresa_id),
            'punto_venta': get_leads_por_punto_venta(conn, empresa_id),
            'temperatura': get_leads_por_temperatura(conn, empresa_id),
            'estado': get_leads_por_estado_gestion(conn, empresa_id),
            'asignacion': get_leads_asignados_vs_no(conn, empresa_id),
            'prioridad': get_distribucion_prioridad(conn, empresa_id),
        }


@st.cache_data(ttl=60)
def cargar_empresas():
    with get_connection() as conn:
        return get_valores_filtros(conn)['empresas']


try:
    empresas = cargar_empresas()
except Exception as exc:
    st.error(f"No fue posible cargar empresas: {exc}")
    st.stop()

# ── Filtro de empresa en sidebar ─────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f"<div style='font-size:0.72rem;font-weight:600;text-transform:uppercase;"
        f"letter-spacing:0.05em;color:{COLORS['text_muted']};margin-bottom:0.5rem;'>"
        f"Filtrar por empresa</div>",
        unsafe_allow_html=True,
    )
    empresa_map = {f"{row['empresa_id']} — {row['nombre']}": row['empresa_id'] for row in empresas}
    seleccion = st.selectbox('Empresa', ['Todas las empresas'] + list(empresa_map), label_visibility="collapsed")
    empresa_id = empresa_map.get(seleccion)

try:
    datos = cargar_datos(empresa_id)
except Exception as exc:
    st.error(f"No fue posible cargar el dashboard: {exc}")
    st.stop()

kpis = datos['kpis']

# ── Sección: KPIs principales ────────────────────────────────────────────────
st.markdown(section_header_html("Resumen operativo"), unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total de leads", f"{kpis['total_leads']:,}")
col2.metric("Pendientes de gestión", f"{kpis['leads_pendientes_gestion']:,}")
col3.metric("Asignados", f"{kpis['leads_asignados']:,}")
col4.metric("Sin asignar", f"{kpis['leads_sin_asignar']:,}")

st.markdown("<div style='margin-top:0.5rem;'></div>", unsafe_allow_html=True)

# ── Sección: Temperatura ─────────────────────────────────────────────────────
st.markdown(section_header_html("Temperatura de leads"), unsafe_allow_html=True)

c_crit, c_alto, c_medio, c_bajo = st.columns(4)
temp_cards = [
    (c_crit, "Crítico",  kpis['leads_criticos'], COLORS['critico_bg'], COLORS['critico_fg'], COLORS['critico_dot'], "#F5B7B1"),
    (c_alto, "Alto",     kpis['leads_altos'],    COLORS['alto_bg'],    COLORS['alto_fg'],    COLORS['alto_dot'],    "#FAD7A0"),
    (c_medio,"Medio",    kpis['leads_medios'],   COLORS['medio_bg'],   COLORS['medio_fg'],   COLORS['medio_dot'],   "#F9E79F"),
    (c_bajo, "Bajo",     kpis['leads_bajos'],    COLORS['bajo_bg'],    COLORS['bajo_fg'],    COLORS['bajo_dot'],    "#A9DFBF"),
]
for col, label, valor, bg, fg, dot, border in temp_cards:
    with col:
        st.markdown(
            f"""<div style="background:{bg};border:1px solid {border};
            border-left:4px solid {dot};border-radius:8px;
            padding:14px 18px;margin-bottom:4px;">
            <div style="font-size:0.68rem;font-weight:600;text-transform:uppercase;
                        letter-spacing:0.05em;color:{fg};margin-bottom:6px;">{label}</div>
            <div style="font-size:1.75rem;font-weight:700;color:{fg};line-height:1.1;">
                {valor:,}</div>
            </div>""",
            unsafe_allow_html=True,
        )

st.markdown("<div style='margin-top:0.5rem;'></div>", unsafe_allow_html=True)

# ── Sección: Asignación visual ───────────────────────────────────────────────
st.markdown(section_header_html("Estado de asignación"), unsafe_allow_html=True)

total = kpis['total_leads'] or 1
pct_asignados = kpis['leads_asignados'] / total
pct_sin = kpis['leads_sin_asignar'] / total

col_bar_a, col_bar_b = st.columns([3, 1])
with col_bar_a:
    st.markdown(
        f"""<div style="margin:6px 0;">
        <div style="display:flex;border-radius:6px;overflow:hidden;height:22px;">
            <div style="flex:{pct_asignados:.4f};background:{COLORS['asignado_fg']};
                        display:flex;align-items:center;justify-content:center;">
                <span style="font-size:0.7rem;font-weight:600;color:#fff;">
                {kpis['leads_asignados']:,} asignados ({pct_asignados:.0%})</span>
            </div>
            <div style="flex:{pct_sin:.4f};background:{COLORS['sinasig_bg']};
                        border:1px solid {COLORS['border']};
                        display:flex;align-items:center;justify-content:center;">
                <span style="font-size:0.7rem;font-weight:600;color:{COLORS['sinasig_fg']};">
                {kpis['leads_sin_asignar']:,} sin asignar ({pct_sin:.0%})</span>
            </div>
        </div>
        </div>""",
        unsafe_allow_html=True,
    )

st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)

# ── Sección: Gráficos ─────────────────────────────────────────────────────────
st.markdown(section_header_html("Distribución de leads"), unsafe_allow_html=True)

izquierda, derecha = st.columns(2)


def grafico_barras_h(titulo: str, filas: list, col_cat: str, col_val: str = "total",
                     color_field: str | None = None, color_map: dict | None = None) -> None:
    """Gráfico de barras horizontales con Altair."""
    df = pd.DataFrame(filas)
    if df.empty:
        st.info("Sin datos.")
        return

    df[col_val] = pd.to_numeric(df[col_val], errors="coerce").fillna(0)
    df = df.sort_values(col_val, ascending=False).head(15)

    # Color semántico si se pide
    if color_field and color_map:
        color_encoding = alt.Color(
            f"{color_field}:N",
            scale=alt.Scale(
                domain=list(color_map.keys()),
                range=list(color_map.values()),
            ),
            legend=None,
        )
    else:
        color_encoding = alt.value(COLORS["primary_light"])

    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
        .encode(
            y=alt.Y(
                f"{col_cat}:N",
                sort="-x",
                axis=alt.Axis(labelLimit=200, labelFontSize=11, ticks=False, domainOpacity=0),
                title=None,
            ),
            x=alt.X(
                f"{col_val}:Q",
                axis=alt.Axis(grid=True, gridOpacity=0.3, labelFontSize=10, ticks=False, domainOpacity=0),
                title=None,
            ),
            color=color_encoding,
            tooltip=[
                alt.Tooltip(f"{col_cat}:N", title=titulo),
                alt.Tooltip(f"{col_val}:Q", title="Leads"),
            ],
        )
        .properties(height=min(30 * len(df) + 40, 380))
        .configure_view(strokeWidth=0)
        .configure_axis(labelColor=COLORS["text_muted"])
    )
    st.altair_chart(chart, use_container_width=True)


with izquierda:
    st.markdown(
        f"<div style='font-size:0.78rem;font-weight:600;color:{COLORS['text_main']};margin-bottom:4px;'>"
        f"Temperatura</div>",
        unsafe_allow_html=True,
    )
    grafico_barras_h(
        "Temperatura", datos['temperatura'], "temperatura",
        color_field="temperatura", color_map=TEMP_COLOR_SCALE,
    )

    st.markdown(
        f"<div style='font-size:0.78rem;font-weight:600;color:{COLORS['text_main']};margin-top:1rem;margin-bottom:4px;'>"
        f"Estado de gestión</div>",
        unsafe_allow_html=True,
    )
    grafico_barras_h("Estado", datos['estado'], "estado_gestion")

with derecha:
    st.markdown(
        f"<div style='font-size:0.78rem;font-weight:600;color:{COLORS['text_main']};margin-bottom:4px;'>"
        f"Por empresa</div>",
        unsafe_allow_html=True,
    )
    grafico_barras_h("Empresa", datos['empresa'], "empresa")

    st.markdown(
        f"<div style='font-size:0.78rem;font-weight:600;color:{COLORS['text_main']};margin-top:1rem;margin-bottom:4px;'>"
        f"Por punto de venta</div>",
        unsafe_allow_html=True,
    )
    grafico_barras_h("Punto de venta", datos['punto_venta'], "punto_venta")

# ── Sección: Ranking de prioridad ────────────────────────────────────────────
st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)
st.markdown(section_header_html("Top 50 leads por prioridad"), unsafe_allow_html=True)

ranking = pd.DataFrame(datos['prioridad'])
if ranking.empty:
    st.info("No hay leads con score actual.")
else:
    ranking['puntaje_prioridad'] = ranking['puntaje_prioridad'].map(
        lambda v: round(float(v), 2)
    )
    # Añadir badge de temperatura como texto enriquecido en columna extra
    ranking['temp_display'] = ranking['temperatura'].fillna('Sin score')

    tabla = ranking.rename(columns={
        'lead_id': 'Lead',
        'nombre_cliente': 'Nombre',
        'empresa': 'Empresa',
        'puntaje_prioridad': 'Score',
        'temp_display': 'Temperatura',
    })[['Lead', 'Nombre', 'Empresa', 'Score', 'Temperatura']]

    # Colorear celdas de temperatura con column_config
    temp_color_map_display = {
        "Crítico": "🔴 Crítico",
        "Alto": "🟠 Alto",
        "Medio": "🟡 Medio",
        "Bajo": "🟢 Bajo",
        "Sin score": "⚪ Sin score",
    }
    tabla['Temperatura'] = tabla['Temperatura'].map(
        lambda t: temp_color_map_display.get(t, t)
    )

    st.dataframe(
        tabla,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Score": st.column_config.NumberColumn(
                "Score",
                format="%.2f",
                help="Puntaje de prioridad operacional (0–100)",
            ),
        },
    )
