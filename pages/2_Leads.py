"""Bandeja operativa de solo lectura respaldada por PostgreSQL."""

import html

import pandas as pd
import streamlit as st

from database import get_connection
from queries.leads_queries import get_leads_bandeja, get_valores_filtros
from styles.theme import COLORS, badge_temperatura, badge_asignacion, get_global_css

st.set_page_config(page_title="Leads — Motos AI Leads", page_icon="📋", layout="wide")
st.markdown(get_global_css(), unsafe_allow_html=True)

c = COLORS

# ── CSS local de la página ──────────────────────────────────────────────────
st.markdown(
    """
    <style>
      [data-testid="stMainBlockContainer"] { max-width: 1440px; padding-top: 1.6rem; }

      /* ── Hero ── */
      .leads-hero {
        background: linear-gradient(135deg, #0F172A 0%, #1B2F4B 100%);
        border: 1px solid #1E3A5F;
        border-radius: 12px;
        padding: 22px 28px;
        margin: .1rem 0 1.4rem;
        box-shadow: 0 4px 20px rgba(15, 23, 42, .18);
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 16px;
      }
      .leads-hero-eyebrow {
        font-size: .68rem;
        font-weight: 700;
        letter-spacing: .1em;
        text-transform: uppercase;
        color: #38BDF8;
        margin-bottom: .45rem;
      }
      .leads-hero-title {
        color: #F8FAFC;
        font-size: 1.45rem;
        font-weight: 800;
        margin: 0 0 .3rem;
        letter-spacing: -.02em;
        line-height: 1.2;
      }
      .leads-hero-sub {
        color: #94A3B8;
        font-size: .82rem;
        line-height: 1.55;
        max-width: 680px;
      }
      .leads-hero-badge {
        background: rgba(56, 189, 248, .12);
        border: 1px solid rgba(56, 189, 248, .35);
        padding: 8px 16px;
        border-radius: 24px;
        color: #7DD3FC;
        font-size: .76rem;
        font-weight: 700;
        white-space: nowrap;
        flex-shrink: 0;
        letter-spacing: .02em;
      }

      /* ── Etiquetas de sección ── */
      .section-label {
        color: #64748B;
        font-size: .72rem;
        font-weight: 700;
        letter-spacing: .09em;
        text-transform: uppercase;
        margin: .15rem 0 .55rem;
      }

      /* ── Caja de filtros principales ── */
      [class*="st-key-filtros-principales"] {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 14px 18px 8px;
        box-shadow: 0 1px 4px rgba(15, 23, 42, .05);
        margin-bottom: 1.1rem;
      }
      [class*="st-key-filtros-principales"] [data-testid="stSelectbox"] [role="group"] {
        background: #F8FAFC !important;
        background-color: #F8FAFC !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 8px !important;
        box-shadow: none !important;
      }
      [class*="st-key-filtros-principales"] [data-testid="stSelectbox"] input {
        color: #0F172A !important;
        background: transparent !important;
        -webkit-text-fill-color: #0F172A !important;
      }
      [class*="st-key-filtros-principales"] [data-testid="stSelectbox"] button {
        color: #64748B !important;
        background: transparent !important;
      }
      [class*="st-key-filtros-principales"] [data-testid="stWidgetLabel"] p {
        color: #475569 !important;
        font-size: .72rem !important;
        font-weight: 700 !important;
        letter-spacing: .04em !important;
        text-transform: uppercase !important;
      }

      /* ── Toolbar (contador + chips) ── */
      .leads-toolbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 16px;
        flex-wrap: wrap;
        margin: .35rem 0 .7rem;
      }
      .leads-count {
        color: #0F172A;
        font-size: 1.1rem;
        font-weight: 800;
        letter-spacing: -.025em;
      }
      .leads-count span {
        color: #64748B;
        font-size: .78rem;
        font-weight: 500;
        letter-spacing: 0;
      }
      .leads-chips {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
      .chip {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 999px;
        padding: 4px 10px;
        font-size: .71rem;
        font-weight: 700;
        color: #334155;
        box-shadow: 0 1px 2px rgba(15, 23, 42, .04);
        white-space: nowrap;
      }
      .chip-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        display: inline-block;
        flex-shrink: 0;
      }

      /* ── Leyenda de temperatura ── */
      .temp-legend {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        align-items: center;
        margin-bottom: .55rem;
      }
      .temp-legend-item {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        font-size: .7rem;
        font-weight: 600;
        color: #475569;
      }
      .temp-legend-swatch {
        width: 10px;
        height: 10px;
        border-radius: 3px;
        display: inline-block;
        flex-shrink: 0;
      }
      .temp-legend-label { color: .64748B; }

      /* ── Contenedor de la tabla ── */
      [class*="st-key-bandeja-tabla"] {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 0 6px 8px;
        box-shadow: 0 1px 4px rgba(15, 23, 42, .05);
      }
      [class*="st-key-bandeja-tabla"] [data-testid="stDataFrame"] {
        border: none !important;
        border-radius: 0 !important;
      }
      .leads-table-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 10px 6px;
        border-bottom: 1px solid #F1F5F9;
        margin-bottom: 4px;
      }
      .leads-table-hint {
        color: #94A3B8;
        font-size: .72rem;
        font-weight: 500;
      }
      .leads-table-total-pill {
        background: #F1F5F9;
        border-radius: 999px;
        padding: 2px 10px;
        font-size: .72rem;
        font-weight: 700;
        color: #334155;
      }

      /* ── Estado vacío ── */
      .leads-empty {
        background: #FFFFFF;
        border: 1px dashed #CBD5E1;
        border-radius: 10px;
        padding: 40px 24px;
        text-align: center;
        color: #64748B;
      }
      .leads-empty strong {
        color: #0F172A;
        display: block;
        font-size: 1rem;
        margin-bottom: .4rem;
      }

      /* ── Panel lead seleccionado ── */
      [class*="st-key-lead-seleccion"] {
        background: linear-gradient(135deg, #F0F9FF 0%, #E0F2FE 100%);
        border: 1px solid #BAE6FD;
        border-left: 4px solid #0EA5E9;
        border-radius: 10px;
        padding: 16px 20px 12px;
        margin-top: 1rem;
        box-shadow: 0 2px 8px rgba(14, 165, 233, .10);
      }
      .leads-select-kicker {
        font-size: .67rem;
        font-weight: 700;
        letter-spacing: .09em;
        text-transform: uppercase;
        color: #0284C7;
        margin-bottom: .3rem;
      }
      .leads-select-name {
        font-size: 1.1rem;
        font-weight: 800;
        color: #0C4A6E;
        margin-bottom: .5rem;
        letter-spacing: -.02em;
      }
      .leads-select-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        align-items: center;
        color: #475569;
        font-size: .79rem;
        margin-bottom: .6rem;
      }
      .leads-select-sep {
        color: #BAE6FD;
        font-size: .7rem;
      }

      /* ── Sidebar botón actualizar ── */
      [data-testid="stSidebar"] [data-testid="stButton"] > button {
        background: #0C4A6E !important;
        border: 1px solid #38BDF8 !important;
        color: #F0F9FF !important;
        font-weight: 700 !important;
        border-radius: 8px !important;
        letter-spacing: .02em !important;
      }
      [data-testid="stSidebar"] [data-testid="stButton"] > button:hover {
        background: #0369A1 !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Hero ─────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <section class="leads-hero">
      <div>
        <div class="leads-hero-eyebrow">Inbox comercial</div>
        <div class="leads-hero-title">Bandeja de leads</div>
        <div class="leads-hero-sub">
          Leads ordenados por prioridad operacional. Aplica filtros, selecciona un registro
          y abre la ficha completa. Esta vista no recalcula scores ni asigna leads.
        </div>
      </div>
      <div class="leads-hero-badge">📋 Solo lectura</div>
    </section>
    """,
    unsafe_allow_html=True,
)


# ── Carga de datos ─────────────────────────────────────────────────────────
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

empresas = {f"{item['empresa_id']} — {item['nombre']}": item['empresa_id'] for item in opciones['empresas']}

# ── Filtros principales (inline, sobre la tabla) ──────────────────────────
st.markdown('<div class="section-label">Filtros principales</div>', unsafe_allow_html=True)

with st.container(key="filtros-principales"):
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

# ── Sidebar (filtros secundarios) ─────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f"<div style='font-size:0.72rem;font-weight:700;text-transform:uppercase;"
        f"letter-spacing:0.08em;color:#94A3B8;margin-bottom:0.5rem;'>"
        f"Filtros adicionales</div>",
        unsafe_allow_html=True,
    )
    busqueda = st.text_input("🔍 Buscar nombre, teléfono o ID")

    st.markdown(
        "<div style='font-size:0.68rem;font-weight:700;text-transform:uppercase;"
        "letter-spacing:0.07em;color:#64748B;margin:0.9rem 0 0.25rem;'>"
        "Temperatura</div>",
        unsafe_allow_html=True,
    )
    temperatura = st.selectbox("Temperatura", ["Todas"] + opciones['temperaturas'], label_visibility="collapsed")

    st.markdown(
        "<div style='font-size:0.68rem;font-weight:700;text-transform:uppercase;"
        "letter-spacing:0.07em;color:#64748B;margin:0.9rem 0 0.25rem;'>"
        "Asignación</div>",
        unsafe_allow_html=True,
    )
    asignacion = st.selectbox("Asignación", ["Todas", "ASIGNADO", "SIN ASIGNAR"], label_visibility="collapsed")

    st.markdown(
        "<div style='font-size:0.68rem;font-weight:700;text-transform:uppercase;"
        "letter-spacing:0.07em;color:#64748B;margin:0.9rem 0 0.25rem;'>"
        "Más filtros</div>",
        unsafe_allow_html=True,
    )
    punto_label = st.selectbox("Punto de venta", ["Todos"] + list(puntos_map))
    canal = st.selectbox("Canal", ["Todos"] + opciones['canales'])
    modelo = st.selectbox("Modelo / SKU", ["Todos"] + opciones['skus'])

    st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)
    if st.button("↺  Actualizar datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── Construir filtros y cargar bandeja ────────────────────────────────────
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

# ── Toolbar: contador + chips de resumen ──────────────────────────────────
st.markdown('<div class="section-label">Resultados de la bandeja</div>', unsafe_allow_html=True)


def contar(serie, valor) -> int:
    if df.empty or serie not in df.columns:
        return 0
    return int((df[serie].fillna("").astype(str) == str(valor)).sum())


n_total = len(df)
n_crit  = contar("temperatura", "Crítico")
n_alto  = contar("temperatura", "Alto")
n_medio = contar("temperatura", "Medio")
n_bajo  = contar("temperatura", "Bajo")
n_asig  = contar("estado_asignacion", "ASIGNADO")
n_sin   = contar("estado_asignacion", "SIN ASIGNAR")

chips = (
    f'<span class="chip"><span class="chip-dot" style="background:#0EA5E9;"></span>{n_total:,} visibles</span>'
    f'<span class="chip"><span class="chip-dot" style="background:{c["critico_dot"]};"></span>{n_crit:,} crítico</span>'
    f'<span class="chip"><span class="chip-dot" style="background:{c["alto_dot"]};"></span>{n_alto:,} alto</span>'
    f'<span class="chip"><span class="chip-dot" style="background:{c["medio_dot"]};"></span>{n_medio:,} medio</span>'
    f'<span class="chip"><span class="chip-dot" style="background:{c["bajo_dot"]};"></span>{n_bajo:,} bajo</span>'
    f'<span class="chip"><span class="chip-dot" style="background:{c["asignado_fg"]};"></span>{n_asig:,} asignados</span>'
    f'<span class="chip"><span class="chip-dot" style="background:{c["sinasig_fg"]};"></span>{n_sin:,} sin asignar</span>'
)

st.markdown(
    f"""
    <div class="leads-toolbar">
      <div class="leads-count">{n_total:,} leads
        <span> · ordenados por prioridad, urgencia y fecha de registro</span>
      </div>
      <div class="leads-chips">{chips}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

if df.empty:
    st.markdown(
        """
        <div class="leads-empty">
          <strong>No hay leads para estos filtros</strong>
          Ajusta empresa, estado o los filtros del panel lateral para ver la bandeja.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

# ── Preparar datos ────────────────────────────────────────────────────────
df["puntaje_prioridad"] = df["puntaje_prioridad"].map(
    lambda value: round(float(value), 2) if pd.notna(value) else None
)


def primer_valor(*valores):
    return next((valor for valor in valores if pd.notna(valor) and str(valor).strip()), "—")


df["modelo"] = df.apply(
    lambda row: primer_valor(row["linea"], row["texto_modelo_original"], row["sku_motocicleta"]),
    axis=1,
)
df["asesor_mostrar"] = df["asesor"].map(lambda valor: valor if pd.notna(valor) else "Sin asignar")

# Temperatura con emoji — el emoji lleva el peso visual en la tabla
temp_emoji_map = {
    "Crítico": "🔴 Crítico",
    "Alto":    "🟠 Alto",
    "Medio":   "🟡 Medio",
    "Bajo":    "🟢 Bajo",
}
df["temp_display"] = df["temperatura"].map(
    lambda t: temp_emoji_map.get(t, "⚪ Sin score") if pd.notna(t) else "⚪ Sin score"
)

asig_emoji_map = {
    "ASIGNADO":    "✓ Asignado",
    "SIN ASIGNAR": "○ Sin asignar",
}
df["asig_display"] = df["estado_asignacion"].map(
    lambda a: asig_emoji_map.get(str(a).upper(), a) if pd.notna(a) else "○ Sin asignar"
)

vista = df[
    [
        "lead_id",
        "nombre_cliente",
        "temp_display",
        "puntaje_prioridad",
        "estado_gestion_normalizado",
        "asig_display",
        "asesor_mostrar",
        "canal",
        "modelo",
        "punto_venta",
        "empresa",
        "registrado_en",
    ]
].rename(
    columns={
        "lead_id":                   "ID",
        "nombre_cliente":            "Nombre",
        "temp_display":              "Temperatura",
        "puntaje_prioridad":         "Score",
        "estado_gestion_normalizado":"Estado",
        "asig_display":              "Asignación",
        "asesor_mostrar":            "Asesor",
        "canal":                     "Canal",
        "modelo":                    "Modelo / SKU",
        "punto_venta":               "Punto de venta",
        "empresa":                   "Empresa",
        "registrado_en":             "Registrado",
    }
)

# ── Leyenda de temperatura encima de la tabla ─────────────────────────────
st.markdown(
    f"""
    <div class="temp-legend">
      <span style="font-size:.7rem;font-weight:700;text-transform:uppercase;
                   letter-spacing:.07em;color:#94A3B8;margin-right:4px;">Temperatura:</span>
      <span class="temp-legend-item">
        <span class="temp-legend-swatch" style="background:{c['critico_dot']};"></span>
        Crítico
      </span>
      <span class="temp-legend-item">
        <span class="temp-legend-swatch" style="background:{c['alto_dot']};"></span>
        Alto
      </span>
      <span class="temp-legend-item">
        <span class="temp-legend-swatch" style="background:{c['medio_dot']};"></span>
        Medio
      </span>
      <span class="temp-legend-item">
        <span class="temp-legend-swatch" style="background:{c['bajo_dot']};"></span>
        Bajo
      </span>
      <span class="temp-legend-item" style="color:#94A3B8;">
        <span class="temp-legend-swatch" style="background:#CBD5E1;"></span>
        Sin score
      </span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Tabla principal ────────────────────────────────────────────────────────
with st.container(key="bandeja-tabla"):
    st.markdown(
        f"""
        <div class="leads-table-header">
          <span class="leads-table-hint">Haz clic en una fila para abrir la ficha del lead</span>
          <span class="leads-table-total-pill">{n_total:,} registros</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    evento = st.dataframe(
        vista,
        use_container_width=True,
        hide_index=True,
        height=430,
        selection_mode="single-row",
        on_select="rerun",
        column_config={
            "ID": st.column_config.TextColumn(
                "ID",
                width="small",
                help="Identificador único del lead",
            ),
            "Nombre": st.column_config.TextColumn(
                "Nombre",
                width="medium",
            ),
            "Temperatura": st.column_config.TextColumn(
                "🌡 Temperatura",
                width="small",
                help="Nivel de urgencia: Crítico > Alto > Medio > Bajo",
            ),
            "Score": st.column_config.NumberColumn(
                "Score ↓",
                format="%.2f",
                help="Puntaje de prioridad operacional (0–100). Tabla ordenada descendente.",
                width="small",
            ),
            "Estado": st.column_config.TextColumn(
                "Estado",
                width="small",
                help="Estado de gestión comercial normalizado",
            ),
            "Asignación": st.column_config.TextColumn(
                "Asignación",
                width="small",
            ),
            "Asesor": st.column_config.TextColumn(
                "Asesor",
                width="medium",
            ),
            "Canal": st.column_config.TextColumn(
                "Canal",
                width="small",
            ),
            "Modelo / SKU": st.column_config.TextColumn(
                "Modelo / SKU",
                width="medium",
            ),
            "Punto de venta": st.column_config.TextColumn(
                "Punto de venta",
                width="medium",
            ),
            "Empresa": st.column_config.TextColumn(
                "Empresa",
                width="small",
            ),
            "Registrado": st.column_config.DatetimeColumn(
                "Registrado",
                format="DD/MM/YY HH:mm",
                width="small",
                help="Fecha y hora de registro del lead",
            ),
        },
    )

# ── Panel de lead seleccionado ────────────────────────────────────────────
seleccion = evento.selection.rows if evento.selection else []
if seleccion:
    fila = df.iloc[seleccion[0]]
    st.session_state["lead_id_seleccionado"] = fila["lead_id"]

    lead_nombre     = fila["nombre_cliente"]
    lead_nombre_safe = html.escape(str(lead_nombre) if pd.notna(lead_nombre) else "lead")
    lead_id_safe    = html.escape(str(fila["lead_id"]))
    asesor_safe     = html.escape(str(fila["asesor_mostrar"]))
    estado_safe     = html.escape(
        str(fila["estado_gestion_normalizado"]) if pd.notna(fila["estado_gestion_normalizado"]) else "—"
    )
    score_txt = f"{fila['puntaje_prioridad']:.2f}" if pd.notna(fila["puntaje_prioridad"]) else "—"
    empresa_safe = html.escape(str(fila.get("empresa", "—") or "—"))
    pv_safe      = html.escape(str(fila.get("punto_venta", "—") or "—"))

    temp_badge_html = badge_temperatura(fila.get("temperatura"))
    asig_badge_html = badge_asignacion(fila.get("estado_asignacion"))

    with st.container(key="lead-seleccion"):
        st.markdown(
            f"""
            <div class="leads-select-kicker">Lead seleccionado</div>
            <div class="leads-select-name">{lead_nombre_safe}</div>
            <div class="leads-select-meta">
              <span style="font-size:.75rem;font-weight:600;color:#0369A1;">#{lead_id_safe}</span>
              <span class="leads-select-sep">·</span>
              {temp_badge_html}
              {asig_badge_html}
              <span class="leads-select-sep">·</span>
              <span>Score&nbsp;<strong style="color:#0C4A6E;">{html.escape(score_txt)}</strong></span>
              <span class="leads-select-sep">·</span>
              <span>{estado_safe}</span>
              <span class="leads-select-sep">·</span>
              <span>{asesor_safe}</span>
              <span class="leads-select-sep">·</span>
              <span style="color:#475569;">{pv_safe} &nbsp;·&nbsp; {empresa_safe}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.page_link(
            "pages/3_Detalle_Lead.py",
            label=f"Ver ficha completa de {lead_nombre}  →",
        )
