"""Página de inicio visual del CRM Motos AI Leads."""

import streamlit as st

from database import get_connection
from queries.dashboard_queries import get_kpis
from styles.theme import get_global_css, COLORS


st.set_page_config(
    page_title="Motos AI Leads — CRM",
    page_icon="🏍️",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(get_global_css(), unsafe_allow_html=True)

# ──────────────────────────────────────────────
# 1. Capa visual CSS (Main + Sidebar + Cards)
# ──────────────────────────────────────────────
st.markdown(
    """
    <style>
      .stApp { background: #F8FAFC; }
      /* El branding del sidebar se renderiza globalmente desde styles/theme.py. */
      .home-sidebar-brand, .home-sidebar-status { display: none !important; }
      [data-testid="stMainBlockContainer"] { max-width: 1440px; padding-top: 2rem; }

      /* Ocultar el ítem redundante 'app' en el menú de Streamlit */
      /* Estilizado del Sidebar */
      /* Hero Banner Layout Flexbox */
      .home-hero {
          background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
          border: 1px solid #334155;
          border-radius: 12px;
          padding: 22px 28px;
          margin: .2rem 0 1.85rem;
          box-shadow: 0 12px 28px rgba(15, 23, 42, .12);
          display: flex;
          justify-content: space-between;
          align-items: center;
      }
      .home-title { color: #F8FAFC; font-size: 1.4rem; font-weight: 700; margin: 0 0 .36rem; }
      .home-subtitle { color: #94A3B8; font-size: .85rem; line-height: 1.5; max-width: 720px; }
      .hero-tag {
          background: rgba(56, 189, 248, 0.1);
          border: 1px solid rgba(56, 189, 248, 0.3);
          padding: 6px 14px;
          border-radius: 20px;
          color: #38BDF8;
          font-size: 0.75rem;
          font-weight: 600;
          white-space: nowrap;
      }

      /* Tarjetas e Indicadores */
      .section-label { color: #64748B; font-size: .75rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; margin: .2rem 0 .75rem; }
      .metric-card { background: #FFF; border: 1px solid #E2E8F0; border-left: 4px solid var(--accent); border-radius: 10px; min-height: 110px; padding: 1rem 1.1rem; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
      .metric-label { color: #64748B; font-size: .72rem; font-weight: 600; letter-spacing: .065em; text-transform: uppercase; }
      .metric-value { color: #0F172A; font-size: 1.85rem; font-weight: 750; letter-spacing: -.04em; line-height: 1.15; margin-top: .35rem; }
      .metric-help { color: #94A3B8; font-size: .75rem; margin-top: .28rem; }

      .temperature-card { background: var(--soft); border: 1px solid var(--line); border-left: 4px solid var(--accent); border-radius: 10px; min-height: 110px; padding: 1rem 1.1rem; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
      .temperature-label { color: var(--ink); font-size: .72rem; font-weight: 700; letter-spacing: .065em; text-transform: uppercase; }
      .temperature-value { color: var(--ink); font-size: 1.85rem; font-weight: 750; letter-spacing: -.04em; line-height: 1.15; margin-top: .35rem; }
      .temperature-help { color: var(--ink); font-size: .72rem; opacity: .85; margin-top: .28rem; }

      /* Tarjetas de Navegación */
      .access-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }
      .nav-card { display: flex; flex-direction: column; min-height: 204px; overflow: hidden; background: #FFF; border: 1px solid #E2E8F0; border-radius: 10px; box-shadow: 0 1px 2px rgba(15,23,42,.04); }
      .nav-card-header { display: flex; align-items: center; gap: 10px; padding: 18px 18px 0; }
      .nav-card-icon { display: inline-flex; align-items: center; justify-content: center; width: 36px; height: 36px; border-radius: 8px; background: #F1F5F9; font-size: 1.1rem; }
      .nav-card-title { color: #0F172A; font-size: .94rem; font-weight: 700; }
      .nav-card-desc { flex: 1; margin: 12px 18px 18px; color: #64748B; font-size: .78rem; line-height: 1.45; }
      .nav-card-btn { display: flex; align-items: center; justify-content: center; min-height: 46px; width: 100%; box-sizing: border-box; background: #0F172A; color: #FFF !important; font-size: .8rem; font-weight: 700; text-decoration: none !important; }
      .nav-card-btn:hover { background: #1E293B; color: #FFF !important; }
      @media (max-width: 900px) { .access-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
      @media (max-width: 560px) { .access-grid { grid-template-columns: 1fr; } }
    </style>
    """,
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────
# 2. Branding y Estado en el Sidebar
# ──────────────────────────────────────────────
if False:  # Reemplazado por la identidad global del sidebar en styles/theme.py.
    st.sidebar.markdown(
    """
    <div class="home-sidebar-brand" style="padding: 12px 8px 18px 8px; border-bottom: 1px solid #1E293B; margin-bottom: 12px;">
        <div style="display: flex; align-items: center; gap: 10px;">
            <div style="font-size: 20px; background: #1E293B; padding: 6px; border-radius: 8px;">🏍️</div>
            <div>
                <div style="color: #F8FAFC; font-size: 1rem; font-weight: 700; line-height: 1.2;">Motos AI Leads</div>
                <div style="display: inline-block; background-color: #0284C7; color: #E0F2FE; font-size: 0.625rem; padding: 2px 6px; border-radius: 4px; font-weight: 600; margin-top: 3px;">CRM INTELLIGENCE</div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if False:  # Reemplazado por la identidad global del sidebar en styles/theme.py.
    st.sidebar.markdown(
    """
    <div class="home-sidebar-status" style="margin-top: 30px; padding: 12px; background-color: #1E293B; border-radius: 8px; border: 1px solid #334155;">
        <div style="color: #38BDF8; font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">Estado del Sistema</div>
        <div style="color: #22C55E; font-size: 0.75rem; font-weight: 500; display: flex; align-items: center; gap: 6px;">
            <span>●</span> PostgreSQL Activo
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if "lead_id_seleccionado" not in st.session_state:
    st.session_state["lead_id_seleccionado"] = None

# ──────────────────────────────────────────────
# 3. Hero Banner Principal
# ──────────────────────────────────────────────
st.markdown(
    """
    <section class="home-hero">
      <div>
        <div class="home-title">Motos AI Leads</div>
        <div class="home-subtitle">Plataforma de priorización inteligente de leads comerciales y asignación automatizada.</div>
      </div>
      <div class="hero-tag">⚡ Operational Pipeline</div>
    </section>
    """,
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────
# Carga de Datos y Métricas
# ──────────────────────────────────────────────
@st.cache_data(ttl=30)
def cargar_kpis():
    with get_connection() as conn:
        return get_kpis(conn)


def tarjeta_metrica(columna, acento, titulo, valor, ayuda):
    with columna:
        st.markdown(
            f'''<div class="metric-card" style="--accent:{acento};">
              <div class="metric-label">{titulo}</div>
              <div class="metric-value">{valor:,}</div>
              <div class="metric-help">{ayuda}</div>
            </div>''',
            unsafe_allow_html=True,
        )


def tarjeta_temperatura(columna, fondo, borde, acento, tinta, titulo, valor, ayuda):
    with columna:
        st.markdown(
            f'''<div class="temperature-card" style="--soft:{fondo};--line:{borde};--accent:{acento};--ink:{tinta};">
              <div class="temperature-label">{titulo}</div>
              <div class="temperature-value">{valor:,}</div>
              <div class="temperature-help">{ayuda}</div>
            </div>''',
            unsafe_allow_html=True,
        )


try:
    kpis = cargar_kpis()

    st.markdown('<div class="section-label">Resumen operativo</div>', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    tarjeta_metrica(col1, "#0EA5E9", "Total leads", kpis["total_leads"], "Capturados en el sistema")
    tarjeta_metrica(col2, "#F59E0B", "Sin asignar", kpis["leads_sin_asignar"], "En cola de distribución")
    tarjeta_metrica(col3, "#10B981", "Asignados", kpis["leads_asignados"], "Acompañamiento comercial")
    tarjeta_metrica(col4, "#6366F1", "Pendientes de gestión", kpis["leads_pendientes_gestion"], "Requieren interacción")

    st.markdown("<div style='height:1.3rem'></div>", unsafe_allow_html=True)
    st.markdown('<div class="section-label">Distribución por temperatura</div>', unsafe_allow_html=True)
    c_crit, c_alto, c_medio, c_bajo = st.columns(4)
    tarjeta_temperatura(c_crit, "#FEF2F2", "#FCA5A5", "#EF4444", "#991B1B", "🔥 Crítico", kpis["leads_criticos"], "Prioridad inmediata")
    tarjeta_temperatura(c_alto, "#FFFBEB", "#FDE68A", "#F59E0B", "#92400E", "⚡ Alto", kpis["leads_altos"], "Atención rápida")
    tarjeta_temperatura(c_medio, "#FEFCE8", "#FEF08A", "#EAB308", "#854D0E", "🌤️ Medio", kpis["leads_medios"], "Seguimiento estándar")
    tarjeta_temperatura(c_bajo, "#ECFDF5", "#A7F3D0", "#10B981", "#065F46", "❄️ Bajo / Nulo", kpis["leads_bajos"], "Baja intencionalidad")

except Exception as e:
    st.error(f"No se pudo conectar a la base de datos: {e}")
    st.stop()

# ──────────────────────────────────────────────
# Módulos Principales
# ──────────────────────────────────────────────
st.markdown("<div style='height:1.7rem'></div>", unsafe_allow_html=True)
st.markdown('<div class="section-label">Módulos principales</div>', unsafe_allow_html=True)

accesos = [
    ("📊", "Dashboard", "Métricas consolidadas, analítica por punto de venta y tendencias.", "Dashboard", "Ver Dashboard  ➔"),
    ("📋", "Bandeja Leads", "Filtra, prioriza y consulta la lista completa de prospectos activos.", "Leads", "Ir a Bandeja  ➔"),
    ("🔍", "Detalle Lead", "Ficha 360°, extracción IA, histórico de scoring y asignación.", "Detalle_Lead", "Consultar Lead  ➔"),
    ("💬", "Simulador WhatsApp", "Prueba el flujo de ingesta, extracción e integración con WhatsApp.", "Simulador_Telegram", "Abrir Simulador  ➔"),
]

tarjetas_acceso = "".join(
    f'''<article class="nav-card">
      <div class="nav-card-header">
        <span class="nav-card-icon">{icono}</span><span class="nav-card-title">{titulo}</span>
      </div>
      <p class="nav-card-desc">{descripcion}</p>
      <a href="{ruta}" target="_self" class="nav-card-btn">{boton}</a>
    </article>'''
    for icono, titulo, descripcion, ruta, boton in accesos
)
st.markdown(f'<div class="access-grid">{tarjetas_acceso}</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# 4. Footer
# ──────────────────────────────────────────────
st.markdown("<div style='height:2rem'></div>", unsafe_allow_html=True)
st.markdown(
    f"""
    <div style="border-top:1px solid {COLORS['border']}; padding-top:1rem; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; color:{COLORS['text_muted']}; font-size:0.75rem;">
        <div><strong>motos-ai-leads</strong> · Sistema de Gestión Comercial con IA</div>
        <div>PostgreSQL · Streamlit · Hybrid Scoring Engine</div>
    </div>
    """,
    unsafe_allow_html=True,
)
