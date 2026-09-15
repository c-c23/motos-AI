"""
pages/1_Dashboard.py
---------------------
Dashboard de indicadores del CRM Motos AI Leads.
Muestra gráficos de distribución de leads por canal, temperatura, asesor y empresa.
"""

import pandas as pd
import streamlit as st
from database import get_connection
from queries.dashboard_queries import (
    get_leads_por_canal,
    get_leads_por_temperatura,
    get_leads_por_asesor,
    get_leads_por_empresa,
    get_distribucion_prioridad,
    get_kpis,
)

st.set_page_config(
    page_title="Dashboard — Motos AI Leads",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Dashboard de indicadores")
st.caption("Resumen de actividad comercial del sistema de leads")
st.divider()

# ──────────────────────────────────────────────
# Carga de datos
# ──────────────────────────────────────────────
@st.cache_data(ttl=30)
def cargar_datos():
    with get_connection() as conn:
        return {
            "kpis":           get_kpis(conn),
            "por_canal":      get_leads_por_canal(conn),
            "por_temperatura": get_leads_por_temperatura(conn),
            "por_asesor":     get_leads_por_asesor(conn),
            "por_empresa":    get_leads_por_empresa(conn),
            "prioridades":    get_distribucion_prioridad(conn),
        }


try:
    datos = cargar_datos()
except Exception as e:
    st.error(f"Error cargando datos: {e}")
    st.stop()

kpis = datos["kpis"]

# ──────────────────────────────────────────────
# Fila de KPIs
# ──────────────────────────────────────────────
c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(8)
c1.metric("Total", kpis["total_leads"])
c2.metric("Nuevos", kpis["leads_nuevos"])
c3.metric("Asignados", kpis["leads_asignados"])
c4.metric("Sin asignar", kpis["leads_sin_asignar"])
c5.metric("🔴 Calientes", kpis["leads_calientes"])
c6.metric("🟡 Tibios", kpis["leads_tibios"])
c7.metric("🔵 Fríos", kpis["leads_frios"])
c8.metric("⚡ Prom. Prioridad", kpis.get("promedio_prioridad", "—"))

st.divider()

# ──────────────────────────────────────────────
# Gráficos — Fila 1
# ──────────────────────────────────────────────
col_izq, col_der = st.columns(2)

with col_izq:
    st.subheader("Leads por canal")
    df_canal = pd.DataFrame(datos["por_canal"])
    if not df_canal.empty:
        st.bar_chart(df_canal.set_index("canal")["total"])
    else:
        st.info("Sin datos")

with col_der:
    st.subheader("Leads por temperatura")
    df_temp = pd.DataFrame(datos["por_temperatura"])
    if not df_temp.empty:
        # Asignar colores según temperatura
        color_map = {"Caliente": "#e74c3c", "Tibio": "#f39c12", "Sin score": "#95a5a6"}
        st.bar_chart(df_temp.set_index("temperatura")["total"])
    else:
        st.info("Sin datos")

st.divider()

# ──────────────────────────────────────────────
# Gráficos — Fila 2
# ──────────────────────────────────────────────
col_izq2, col_der2 = st.columns(2)

with col_izq2:
    st.subheader("Leads por asesor")
    df_asesor = pd.DataFrame(datos["por_asesor"])
    if not df_asesor.empty:
        st.bar_chart(df_asesor.set_index("asesor")["total"])
    else:
        st.info("Sin datos")

with col_der2:
    st.subheader("Leads por empresa")
    df_empresa = pd.DataFrame(datos["por_empresa"])
    if not df_empresa.empty:
        st.bar_chart(df_empresa.set_index("empresa")["total"])
    else:
        st.info("Sin datos")

st.divider()

# ──────────────────────────────────────────────
# Tabla de prioridades
# ──────────────────────────────────────────────
st.subheader("Ranking de prioridad de leads")
df_prio = pd.DataFrame(datos["prioridades"])
if not df_prio.empty:
    df_prio["puntaje_prioridad"] = df_prio["puntaje_prioridad"].apply(
        lambda x: round(float(x), 2) if x else None
    )
    st.dataframe(
        df_prio.rename(columns={
            "lead_id": "Lead",
            "nombre_cliente": "Cliente",
            "puntaje_prioridad": "Prioridad",
            "temperatura": "Temperatura",
        }),
        use_container_width=True,
        hide_index=True,
    )
