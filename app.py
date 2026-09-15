"""
app.py
------
Entrypoint del CRM Motos AI Leads en Streamlit.
Página de inicio con KPIs resumen y acceso a la navegación.
"""

import streamlit as st
from database import get_connection
from queries.dashboard_queries import get_kpis

# ──────────────────────────────────────────────
# Configuración de la página
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Motos AI Leads — CRM",
    page_icon="🏍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# Inicializar session_state para navegación
# ──────────────────────────────────────────────
if "lead_id_seleccionado" not in st.session_state:
    st.session_state["lead_id_seleccionado"] = None

# ──────────────────────────────────────────────
# Encabezado
# ──────────────────────────────────────────────
st.title("🏍️ Motos AI Leads")
st.caption("Sistema de gestión inteligente de leads para venta de motocicletas")
st.divider()

# ──────────────────────────────────────────────
# Carga de KPIs
# ──────────────────────────────────────────────
@st.cache_data(ttl=30)
def cargar_kpis():
    with get_connection() as conn:
        return get_kpis(conn)


try:
    kpis = cargar_kpis()

    # Fila 1: métricas principales
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Leads", kpis["total_leads"])
    col2.metric("Leads Nuevos", kpis["leads_nuevos"])
    col3.metric("Asignados", kpis["leads_asignados"])
    col4.metric("Sin Asignar", kpis["leads_sin_asignar"])

    st.write("")

    # Fila 2: temperatura
    col5, col6, col7 = st.columns(3)
    col5.metric("🔴 Calientes", kpis["leads_calientes"])
    col6.metric("🟡 Tibios", kpis["leads_tibios"])
    col7.metric("🔵 Fríos / Sin score", kpis["leads_frios"])

except Exception as e:
    st.error(f"No se pudo conectar a la base de datos: {e}")
    st.stop()

# ──────────────────────────────────────────────
# Navegación rápida
# ──────────────────────────────────────────────
st.divider()
st.subheader("Accesos rápidos")

col_a, col_b, col_c = st.columns(3)
with col_a:
    st.page_link("pages/1_Dashboard.py", label="📊 Dashboard de indicadores", icon="📊")
with col_b:
    st.page_link("pages/2_Leads.py", label="📋 Bandeja de leads", icon="📋")
with col_c:
    st.page_link("pages/3_Detalle_Lead.py", label="🔍 Detalle de un lead", icon="🔍")

# ──────────────────────────────────────────────
# Footer
# ──────────────────────────────────────────────
st.divider()
st.caption("motos-ai-leads · Prototipo CRM · PostgreSQL 18.6 · Streamlit")
