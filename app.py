"""
app.py
------
Entrypoint del CRM Motos AI Leads en Streamlit.
Página de inicio con KPIs resumen y acceso a la navegación.
"""

import streamlit as st
from database import get_connection
from queries.dashboard_queries import get_kpis
from styles.theme import get_global_css, COLORS, badge_temperatura

# ──────────────────────────────────────────────
# Configuración de la página
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Motos AI Leads — CRM",
    page_icon="🏍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(get_global_css(), unsafe_allow_html=True)

# ──────────────────────────────────────────────
# Inicializar session_state para navegación
# ──────────────────────────────────────────────
if "lead_id_seleccionado" not in st.session_state:
    st.session_state["lead_id_seleccionado"] = None

# ──────────────────────────────────────────────
# Encabezado
# ──────────────────────────────────────────────
col_logo, col_title = st.columns([1, 11])
with col_logo:
    st.markdown(
        "<div style='font-size:2.4rem;line-height:1;padding-top:6px;'>🏍️</div>",
        unsafe_allow_html=True,
    )
with col_title:
    st.markdown(
        f"""
        <div>
            <div style='font-size:1.5rem;font-weight:700;color:{COLORS["text_main"]};
                        line-height:1.2;'>Motos AI Leads</div>
            <div style='font-size:0.82rem;color:{COLORS["text_muted"]};margin-top:2px;'>
                Priorización inteligente de leads comerciales · CRM operativo
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# Carga de KPIs
# ──────────────────────────────────────────────
@st.cache_data(ttl=30)
def cargar_kpis():
    with get_connection() as conn:
        return get_kpis(conn)


try:
    kpis = cargar_kpis()

    # ── Fila 1: métricas principales ──────────
    st.markdown(
        f"<div style='font-size:0.72rem;font-weight:600;text-transform:uppercase;"
        f"letter-spacing:0.07em;color:{COLORS['text_muted']};margin-bottom:0.6rem;'>"
        f"Resumen operativo</div>",
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total leads", f"{kpis['total_leads']:,}")
    col2.metric("Sin asignar", f"{kpis['leads_sin_asignar']:,}")
    col3.metric("Asignados", f"{kpis['leads_asignados']:,}")
    col4.metric("Pendientes de gestión", f"{kpis['leads_pendientes_gestion']:,}")

    st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)

    # ── Fila 2: temperatura ────────────────────
    st.markdown(
        f"<div style='font-size:0.72rem;font-weight:600;text-transform:uppercase;"
        f"letter-spacing:0.07em;color:{COLORS['text_muted']};margin-bottom:0.6rem;'>"
        f"Distribución por temperatura</div>",
        unsafe_allow_html=True,
    )

    c_crit, c_alto, c_medio, c_bajo = st.columns(4)

    with c_crit:
        st.markdown(
            f"""<div style="background:{COLORS['critico_bg']};border:1px solid #F5B7B1;
            border-left:4px solid {COLORS['critico_dot']};border-radius:8px;
            padding:14px 18px;margin-bottom:4px;">
            <div style="font-size:0.68rem;font-weight:600;text-transform:uppercase;
                        letter-spacing:0.05em;color:{COLORS['critico_fg']};margin-bottom:6px;">
                Crítico</div>
            <div style="font-size:1.75rem;font-weight:700;color:{COLORS['critico_fg']};
                        line-height:1.1;">{kpis['leads_criticos']:,}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    with c_alto:
        st.markdown(
            f"""<div style="background:{COLORS['alto_bg']};border:1px solid #FAD7A0;
            border-left:4px solid {COLORS['alto_dot']};border-radius:8px;
            padding:14px 18px;margin-bottom:4px;">
            <div style="font-size:0.68rem;font-weight:600;text-transform:uppercase;
                        letter-spacing:0.05em;color:{COLORS['alto_fg']};margin-bottom:6px;">
                Alto</div>
            <div style="font-size:1.75rem;font-weight:700;color:{COLORS['alto_fg']};
                        line-height:1.1;">{kpis['leads_altos']:,}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    with c_medio:
        st.markdown(
            f"""<div style="background:{COLORS['medio_bg']};border:1px solid #F9E79F;
            border-left:4px solid {COLORS['medio_dot']};border-radius:8px;
            padding:14px 18px;margin-bottom:4px;">
            <div style="font-size:0.68rem;font-weight:600;text-transform:uppercase;
                        letter-spacing:0.05em;color:{COLORS['medio_fg']};margin-bottom:6px;">
                Medio</div>
            <div style="font-size:1.75rem;font-weight:700;color:{COLORS['medio_fg']};
                        line-height:1.1;">{kpis['leads_medios']:,}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    with c_bajo:
        st.markdown(
            f"""<div style="background:{COLORS['bajo_bg']};border:1px solid #A9DFBF;
            border-left:4px solid {COLORS['bajo_dot']};border-radius:8px;
            padding:14px 18px;margin-bottom:4px;">
            <div style="font-size:0.68rem;font-weight:600;text-transform:uppercase;
                        letter-spacing:0.05em;color:{COLORS['bajo_fg']};margin-bottom:6px;">
                Bajo</div>
            <div style="font-size:1.75rem;font-weight:700;color:{COLORS['bajo_fg']};
                        line-height:1.1;">{kpis['leads_bajos']:,}</div>
            </div>""",
            unsafe_allow_html=True,
        )

except Exception as e:
    st.error(f"No se pudo conectar a la base de datos: {e}")
    st.stop()

# ──────────────────────────────────────────────
# Navegación rápida
# ──────────────────────────────────────────────
st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)
st.markdown(
    f"<div style='font-size:0.72rem;font-weight:600;text-transform:uppercase;"
    f"letter-spacing:0.07em;color:{COLORS['text_muted']};margin-bottom:0.6rem;'>"
    f"Accesos rápidos</div>",
    unsafe_allow_html=True,
)

col_a, col_b, col_c, col_d = st.columns(4)
with col_a:
    st.page_link("pages/1_Dashboard.py", label="📊 Dashboard de indicadores")
with col_b:
    st.page_link("pages/2_Leads.py", label="📋 Bandeja de leads")
with col_c:
    st.page_link("pages/3_Detalle_Lead.py", label="🔍 Detalle de un lead")
with col_d:
    st.page_link("pages/4_Simulador_Telegram.py", label="💬 Simulador Telegram")

# ──────────────────────────────────────────────
# Footer
# ──────────────────────────────────────────────
st.markdown("<div style='margin-top:2rem;'></div>", unsafe_allow_html=True)
st.markdown(
    f"<div style='font-size:0.72rem;color:{COLORS['text_light']};border-top:1px solid "
    f"{COLORS['border']};padding-top:0.75rem;'>"
    f"motos-ai-leads &nbsp;·&nbsp; CRM Priorización Comercial &nbsp;·&nbsp; "
    f"PostgreSQL &nbsp;·&nbsp; Streamlit 1.63</div>",
    unsafe_allow_html=True,
)
