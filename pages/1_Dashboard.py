"""Dashboard operacional: agregados de PostgreSQL, sin lógica de negocio."""

import pandas as pd
import streamlit as st

from database import get_connection
from queries.dashboard_queries import (
    get_distribucion_prioridad, get_kpis, get_leads_asignados_vs_no,
    get_leads_por_empresa, get_leads_por_estado_gestion, get_leads_por_punto_venta,
    get_leads_por_temperatura,
)
from queries.leads_queries import get_valores_filtros

st.set_page_config(page_title="Dashboard — Motos AI Leads", page_icon="📊", layout="wide")
st.title("📊 Dashboard operativo")
st.caption("Indicadores agregados directamente desde PostgreSQL.")


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

empresa_map = {f"{row['empresa_id']} — {row['nombre']}": row['empresa_id'] for row in empresas}
seleccion = st.sidebar.selectbox('Empresa', ['Todas las empresas'] + list(empresa_map))
empresa_id = empresa_map.get(seleccion)
try:
    datos = cargar_datos(empresa_id)
except Exception as exc:
    st.error(f"No fue posible cargar el dashboard: {exc}")
    st.stop()

kpis = datos['kpis']
st.subheader('KPIs')
fila1 = st.columns(4)
fila1[0].metric('Total de leads', kpis['total_leads'])
fila1[1].metric('Pendientes de gestión', kpis['leads_pendientes_gestion'])
fila1[2].metric('Asignados', kpis['leads_asignados'])
fila1[3].metric('Sin asignar', kpis['leads_sin_asignar'])
fila2 = st.columns(4)
fila2[0].metric('Críticos', kpis['leads_criticos'])
fila2[1].metric('Altos', kpis['leads_altos'])
fila2[2].metric('Medios', kpis['leads_medios'])
fila2[3].metric('Bajos', kpis['leads_bajos'])


def grafico(titulo, filas, etiqueta):
    st.subheader(titulo)
    df = pd.DataFrame(filas)
    if df.empty:
        st.info('Sin datos.')
    else:
        st.bar_chart(df.set_index(etiqueta)['total'])


izquierda, derecha = st.columns(2)
with izquierda:
    grafico('Leads por empresa', datos['empresa'], 'empresa')
    grafico('Leads por temperatura', datos['temperatura'], 'temperatura')
    grafico('Asignados vs. no asignados', datos['asignacion'], 'estado_asignacion')
with derecha:
    grafico('Leads por punto de venta', datos['punto_venta'], 'punto_venta')
    grafico('Leads por estado de gestión', datos['estado'], 'estado_gestion')

st.subheader('Ranking de prioridad')
ranking = pd.DataFrame(datos['prioridad'])
if ranking.empty:
    st.info('No hay leads con score actual.')
else:
    ranking['puntaje_prioridad'] = ranking['puntaje_prioridad'].map(lambda value: round(float(value), 2))
    st.dataframe(ranking.rename(columns={
        'lead_id': 'Lead', 'nombre_cliente': 'Nombre', 'empresa': 'Empresa',
        'puntaje_prioridad': 'Prioridad', 'temperatura': 'Temperatura',
    }), use_container_width=True, hide_index=True)
