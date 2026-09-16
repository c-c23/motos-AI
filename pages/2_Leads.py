"""Bandeja operativa de solo lectura respaldada por PostgreSQL."""

import pandas as pd
import streamlit as st

from database import get_connection
from queries.leads_queries import get_leads_bandeja, get_valores_filtros
from styles.theme import COLORS, badge_temperatura, badge_asignacion, get_global_css

st.set_page_config(page_title="Leads — Motos AI Leads", page_icon="📋", layout="wide")
st.markdown(get_global_css(), unsafe_allow_html=True)

# ── Encabezado ───────────────────────────────────────────────────────────────
st.markdown(
    f"<h1 style='margin-bottom:2px;'>Bandeja de leads</h1>"
    f"<div style='font-size:0.82rem;color:{COLORS['text_muted']};margin-bottom:1.5rem;'>"
    f"Leads ordenados por prioridad · Esta página no recalcula scores ni asigna leads</div>",
    unsafe_allow_html=True,
)


# ── Carga ─────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def cargar_filtros():
    with get_connection() as conn:
        return get_valores_filtros(conn)


@st.cache_data(ttl=30)
def cargar_bandeja(**filtros):
    with get_connection() as conn:
        return get_leads_bandeja(conn, **filtros)


try:
    opciones = cargar_filtros()
except Exception as exc:
    st.error(f"No fue posible cargar los filtros: {exc}")
    st.stop()

# ── Sidebar de filtros ────────────────────────────────────────────────────────
empresas = {f"{item['empresa_id']} — {item['nombre']}": item['empresa_id'] for item in opciones['empresas']}

st.markdown(
    """
    <style>
    [class*="st-key-filtros-principales"] [data-baseweb="select"],
    [class*="st-key-filtros-principales"] [data-baseweb="select"] > div {
        background: #FFFFFF !important;
        background-color: #FFFFFF !important;
        border-color: #CBD5E1 !important;
        color: #1A1D23 !important;
    }
    [class*="st-key-filtros-principales"] [data-baseweb="select"] [data-testid="stMarkdownContainer"] p,
    [class*="st-key-filtros-principales"] [data-baseweb="select"] input {
        color: #1A1D23 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.container(key="filtros-principales"):
    st.markdown(
        f"<div style='font-size:0.72rem;font-weight:600;text-transform:uppercase;"
        f"letter-spacing:0.05em;color:{COLORS['text_muted']};margin-bottom:0.5rem;'>"
        f"Filtros principales</div>",
        unsafe_allow_html=True,
    )
    empresa_col, asesor_col, estado_col = st.columns(3)
    empresas_filtro = ["Todas"] + list(empresas)
    empresa_inicial = "EMP-01 — Motos Andinas"
    empresa_index = empresas_filtro.index(empresa_inicial) if empresa_inicial in empresas_filtro else 0

    with empresa_col:
        empresa_label = st.selectbox("Empresa", empresas_filtro, index=empresa_index)
    empresa_id = empresas.get(empresa_label)

    puntos = [item for item in opciones['puntos_venta'] if not empresa_id or item['empresa_id'] == empresa_id]
    puntos_map = {f"{item['punto_venta_id']} — {item['nombre']}": item['punto_venta_id'] for item in puntos}
    asesores = [item for item in opciones['asesores'] if not empresa_id or item['empresa_id'] == empresa_id]
    asesores_map = {f"{item['asesor_id']} — {item['nombre']}": item['asesor_id'] for item in asesores}

    with asesor_col:
        asesor_label = st.selectbox("Asesor", ["Todos"] + list(asesores_map))

    estados_filtro = ["Todos"] + opciones['estados_normalizados']
    estado_inicial = "Sin gestión"
    estado_index = estados_filtro.index(estado_inicial) if estado_inicial in estados_filtro else 0

    with estado_col:
        estado = st.selectbox("Estado de gestión", estados_filtro, index=estado_index)

with st.sidebar:
    st.markdown(
        f"<div style='font-size:0.72rem;font-weight:600;text-transform:uppercase;"
        f"letter-spacing:0.05em;color:{COLORS['text_muted']};margin-bottom:0.5rem;'>"
        f"Filtros</div>",
        unsafe_allow_html=True,
    )
    busqueda = st.text_input("🔍 Buscar nombre, teléfono o ID")

    st.markdown(
        f"<div style='font-size:0.68rem;font-weight:600;text-transform:uppercase;"
        f"letter-spacing:0.05em;color:{COLORS['text_light']};margin:0.75rem 0 0.25rem;'>"
        f"Temperatura</div>",
        unsafe_allow_html=True,
    )
    temperatura = st.selectbox("Temperatura", ["Todas"] + opciones['temperaturas'], label_visibility="collapsed")

    st.markdown(
        f"<div style='font-size:0.68rem;font-weight:600;text-transform:uppercase;"
        f"letter-spacing:0.05em;color:{COLORS['text_light']};margin:0.75rem 0 0.25rem;'>"
        f"Asignación</div>",
        unsafe_allow_html=True,
    )
    asignacion = st.selectbox("Asignación", ["Todas", "ASIGNADO", "SIN ASIGNAR"], label_visibility="collapsed")

    st.markdown(
        f"<div style='font-size:0.68rem;font-weight:600;text-transform:uppercase;"
        f"letter-spacing:0.05em;color:{COLORS['text_light']};margin:0.75rem 0 0.25rem;'>"
        f"Otros filtros</div>",
        unsafe_allow_html=True,
    )
    punto_label = st.selectbox("Punto de venta", ["Todos"] + list(puntos_map))
    canal = st.selectbox("Canal", ["Todos"] + opciones['canales'])
    modelo = st.selectbox("Modelo / SKU", ["Todos"] + opciones['skus'])

    st.markdown("<div style='margin-top:0.75rem;'></div>", unsafe_allow_html=True)
    if st.button("↺ Actualizar datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── Cargar bandeja ────────────────────────────────────────────────────────────
filtros = {
    "busqueda": busqueda or None,
    "empresa_id": empresa_id,
    "punto_venta_id": puntos_map.get(punto_label),
    "asesor_id": asesores_map.get(asesor_label),
    "canal": None if canal == "Todos" else canal,
    "temperatura": None if temperatura == "Todas" else temperatura,
    "estado_gestion": None if estado == "Todos" else estado,
    "asignacion": None if asignacion == "Todas" else asignacion,
    "sku": None if modelo == "Todos" else modelo,
}

try:
    filas = cargar_bandeja(**filtros)
except Exception as exc:
    st.error(f"No fue posible cargar la bandeja: {exc}")
    st.stop()

df = pd.DataFrame(filas)

# ── Contador de resultados ────────────────────────────────────────────────────
total_str = f"{len(df):,}"
st.markdown(
    f"<div style='font-size:0.8rem;color:{COLORS['text_muted']};margin-bottom:0.75rem;'>"
    f"<b style='color:{COLORS['text_main']};'>{total_str}</b> leads encontrados "
    f"&nbsp;·&nbsp; ordenados por prioridad, urgencia y fecha de registro</div>",
    unsafe_allow_html=True,
)

if df.empty:
    st.info("No hay leads para los filtros seleccionados.")
    st.stop()

# ── Preparar datos de la tabla ────────────────────────────────────────────────
df['puntaje_prioridad'] = df['puntaje_prioridad'].map(
    lambda value: round(float(value), 2) if pd.notna(value) else None
)


def primer_valor(*valores):
    return next((valor for valor in valores if pd.notna(valor) and str(valor).strip()), '—')


df['modelo'] = df.apply(
    lambda row: primer_valor(row['linea'], row['texto_modelo_original'], row['sku_motocicleta']),
    axis=1,
)
df['asesor_mostrar'] = df['asesor'].map(lambda valor: valor if pd.notna(valor) else 'Sin asignar')

# Representación de temperatura con emoji para la tabla nativa
temp_emoji_map = {
    "Crítico":  "🔴 Crítico",
    "Alto":     "🟠 Alto",
    "Medio":    "🟡 Medio",
    "Bajo":     "🟢 Bajo",
}
df['temp_display'] = df['temperatura'].map(
    lambda t: temp_emoji_map.get(t, "⚪ Sin score") if pd.notna(t) else "⚪ Sin score"
)

# Representación de asignación con emoji
asig_emoji_map = {
    "ASIGNADO":    "✓ Asignado",
    "SIN ASIGNAR": "○ Sin asignar",
}
df['asig_display'] = df['estado_asignacion'].map(
    lambda a: asig_emoji_map.get(str(a).upper(), a) if pd.notna(a) else "○ Sin asignar"
)

vista = df[[
    'lead_id', 'nombre_cliente', 'empresa', 'punto_venta', 'canal',
    'modelo', 'puntaje_prioridad', 'temp_display', 'estado_gestion_normalizado',
    'asig_display', 'asesor_mostrar', 'registrado_en',
]].rename(columns={
    'lead_id': 'ID',
    'nombre_cliente': 'Nombre',
    'empresa': 'Empresa',
    'punto_venta': 'Punto de venta',
    'modelo': 'Modelo / SKU',
    'puntaje_prioridad': 'Score',
    'temp_display': 'Temperatura',
    'estado_gestion_normalizado': 'Estado',
    'asig_display': 'Asignación',
    'asesor_mostrar': 'Asesor',
    'registrado_en': 'Registrado',
})

# ── Tabla ─────────────────────────────────────────────────────────────────────
evento = st.dataframe(
    vista,
    use_container_width=True,
    hide_index=True,
    selection_mode='single-row',
    on_select='rerun',
    column_config={
        "Score": st.column_config.NumberColumn(
            "Score",
            format="%.2f",
            help="Puntaje de prioridad operacional (mayor = más prioritario)",
            width="small",
        ),
        "ID": st.column_config.TextColumn("ID", width="small"),
        "Temperatura": st.column_config.TextColumn("Temperatura", width="medium"),
        "Asignación": st.column_config.TextColumn("Asignación", width="medium"),
        "Registrado": st.column_config.DatetimeColumn("Registrado", format="DD/MM/YY HH:mm"),
    },
)

# ── Selección de fila → navegación a detalle ─────────────────────────────────
seleccion = evento.selection.rows if evento.selection else []
if seleccion:
    st.session_state['lead_id_seleccionado'] = df.iloc[seleccion[0]]['lead_id']
    lead_nombre = df.iloc[seleccion[0]]['nombre_cliente']
    st.markdown(
        f"<div style='margin-top:0.75rem;'></div>",
        unsafe_allow_html=True,
    )
    st.page_link(
        'pages/3_Detalle_Lead.py',
        label=f'🔎 Ver ficha completa de {lead_nombre} →',
    )
