"""
pages/2_Leads.py
-----------------
Bandeja principal de leads del CRM Motos AI Leads.
Lista leads ordenados por prioridad, con filtros y búsqueda.
Al seleccionar un lead, guarda el lead_id en session_state
para que la página de detalle lo pueda leer.
"""

import pandas as pd
import streamlit as st
from database import get_connection
from queries.leads_queries import get_leads, get_valores_filtros

st.set_page_config(
    page_title="Leads — Motos AI Leads",
    page_icon="📋",
    layout="wide",
)

st.title("📋 Bandeja de leads")
st.caption("Leads ordenados por puntaje de prioridad (mayor primero)")

# ──────────────────────────────────────────────
# Carga de datos
# ──────────────────────────────────────────────
@st.cache_data(ttl=30)
def cargar_leads():
    with get_connection() as conn:
        leads = get_leads(conn)
        filtros = get_valores_filtros(conn)
    return leads, filtros


try:
    leads_raw, filtros = cargar_leads()
except Exception as e:
    st.error(f"Error cargando leads: {e}")
    st.stop()

df = pd.DataFrame(leads_raw)

# ──────────────────────────────────────────────
# Sidebar — Filtros
# ──────────────────────────────────────────────
with st.sidebar:
    st.header("Filtros")

    busqueda = st.text_input("Buscar por nombre o teléfono", "")

    temperaturas_sel = st.multiselect(
        "Temperatura",
        options=filtros["temperaturas"],
        default=[],
    )
    canales_sel = st.multiselect(
        "Canal",
        options=filtros["canales"],
        default=[],
    )
    empresas_sel = st.multiselect(
        "Empresa",
        options=filtros["empresas"],
        default=[],
    )
    puntos_sel = st.multiselect(
        "Punto de venta",
        options=filtros["puntos_venta"],
        default=[],
    )
    asesores_sel = st.multiselect(
        "Asesor",
        options=filtros["asesores"],
        default=[],
    )
    estados_sel = st.multiselect(
        "Estado de gestión",
        options=filtros["estados"],
        default=[],
    )

    if st.button("Limpiar filtros"):
        st.rerun()

# ──────────────────────────────────────────────
# Aplicar filtros
# ──────────────────────────────────────────────
df_filtrado = df.copy()

if busqueda:
    mask = (
        df_filtrado["nombre_cliente"].str.contains(busqueda, case=False, na=False)
        | df_filtrado["telefono"].str.contains(busqueda, case=False, na=False)
    )
    df_filtrado = df_filtrado[mask]

if temperaturas_sel:
    df_filtrado = df_filtrado[df_filtrado["temperatura"].isin(temperaturas_sel)]
if canales_sel:
    df_filtrado = df_filtrado[df_filtrado["canal"].isin(canales_sel)]
if empresas_sel:
    df_filtrado = df_filtrado[df_filtrado["empresa"].isin(empresas_sel)]
if puntos_sel:
    df_filtrado = df_filtrado[df_filtrado["punto_venta"].isin(puntos_sel)]
if asesores_sel:
    df_filtrado = df_filtrado[df_filtrado["asesor"].isin(asesores_sel)]
if estados_sel:
    df_filtrado = df_filtrado[df_filtrado["estado_gestion"].isin(estados_sel)]

st.caption(f"Mostrando {len(df_filtrado)} de {len(df)} leads")

# ──────────────────────────────────────────────
# Función para badge de temperatura
# ──────────────────────────────────────────────
def badge_temperatura(t):
    if t == "Crítico":
        return "🔴 Crítico"
    elif t == "Alto":
        return "🟠 Alto"
    elif t == "Medio":
        return "🟡 Medio"
    elif t == "Bajo":
        return "🔵 Bajo"
    elif t == "Caliente":
        return "🔴 Caliente"
    elif t == "Tibio":
        return "🟡 Tibio"
    elif t == "Frio":
        return "🔵 Frío"
    return "⚪ Sin score"


def formatear_precio(v):
    if v is None:
        return "—"
    return f"${int(v):,}".replace(",", ".")


# ──────────────────────────────────────────────
# Tabla de leads
# ──────────────────────────────────────────────
if df_filtrado.empty:
    st.info("No hay leads que coincidan con los filtros seleccionados.")
else:
    # Preparar columnas para mostrar
    df_vista = df_filtrado[[
        "lead_id", "puntaje_prioridad", "temperatura", "modelo_scoring", "nombre_cliente",
        "telefono", "canal", "linea", "marca", "pago_inicial",
        "metodo_pago", "asesor", "estado_gestion",
    ]].copy()

    df_vista["temperatura"] = df_vista["temperatura"].apply(badge_temperatura)
    df_vista["puntaje_prioridad"] = df_vista["puntaje_prioridad"].apply(
        lambda x: round(float(x), 2) if x else None
    )
    df_vista["modelo_scoring"] = df_vista["modelo_scoring"].fillna("rules")
    df_vista["pago_inicial"] = df_vista["pago_inicial"].apply(formatear_precio)
    df_vista["moto"] = df_vista.apply(
        lambda r: f"{r['marca']} {r['linea']}" if r["marca"] else "—", axis=1
    )
    df_vista["metodo_pago"] = df_vista["metodo_pago"].fillna("—")
    df_vista["asesor"] = df_vista["asesor"].fillna("Sin asignar")

    df_mostrar = df_vista[[
        "lead_id", "puntaje_prioridad", "temperatura", "modelo_scoring", "nombre_cliente",
        "telefono", "canal", "moto", "pago_inicial", "metodo_pago",
        "asesor", "estado_gestion",
    ]].rename(columns={
        "lead_id":           "ID",
        "puntaje_prioridad": "Prioridad",
        "temperatura":       "Temperatura",
        "modelo_scoring":    "Modelo",
        "nombre_cliente":    "Cliente",
        "telefono":          "Teléfono",
        "canal":             "Canal",
        "moto":              "Moto",
        "pago_inicial":      "Inicial",
        "metodo_pago":       "Pago",
        "asesor":            "Asesor",
        "estado_gestion":    "Estado",
    })

    # Mostrar tabla con selección de filas
    event = st.dataframe(
        df_mostrar,
        use_container_width=True,
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun",
        key="tabla_leads",
    )

    # ──────────────────────────────────────────────
    # Selección de lead → navegar a detalle
    # ──────────────────────────────────────────────
    filas_sel = event.selection.rows if event.selection else []
    if filas_sel:
        idx = filas_sel[0]
        lead_id = df_filtrado.iloc[idx]["lead_id"]
        st.session_state["lead_id_seleccionado"] = lead_id
        st.info(f"Lead seleccionado: **{lead_id}** — Ve a la página **Detalle Lead** para ver la ficha completa.")
        st.page_link("pages/3_Detalle_Lead.py", label="Ver detalle del lead →", icon="🔍")
