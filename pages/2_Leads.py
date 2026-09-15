"""Bandeja operativa de solo lectura respaldada por PostgreSQL."""

import pandas as pd
import streamlit as st

from database import get_connection
from queries.leads_queries import get_leads_bandeja, get_valores_filtros

st.set_page_config(page_title="Leads — Motos AI Leads", page_icon="📋", layout="wide")
st.title("📋 Bandeja de leads")
st.caption("Datos operativos persistidos; esta página no calcula scores ni asigna leads.")


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
empresa_label = st.sidebar.selectbox("Empresa", ["Todas"] + list(empresas))
empresa_id = empresas.get(empresa_label)
puntos = [item for item in opciones['puntos_venta'] if not empresa_id or item['empresa_id'] == empresa_id]
puntos_map = {f"{item['punto_venta_id']} — {item['nombre']}": item['punto_venta_id'] for item in puntos}
asesores = [item for item in opciones['asesores'] if not empresa_id or item['empresa_id'] == empresa_id]
asesores_map = {f"{item['asesor_id']} — {item['nombre']}": item['asesor_id'] for item in asesores}

with st.sidebar:
    st.header("Filtros")
    busqueda = st.text_input("Buscar nombre, teléfono o ID")
    punto_label = st.selectbox("Punto de venta", ["Todos"] + list(puntos_map))
    asesor_label = st.selectbox("Asesor", ["Todos"] + list(asesores_map))
    canal = st.selectbox("Canal", ["Todos"] + opciones['canales'])
    temperatura = st.selectbox("Temperatura", ["Todas"] + opciones['temperaturas'])
    estado = st.selectbox("Estado de gestión", ["Todos"] + opciones['estados_normalizados'])
    asignacion = st.selectbox("Asignación", ["Todas", "ASIGNADO", "SIN ASIGNAR"])
    modelo = st.selectbox("Modelo / SKU", ["Todos"] + opciones['skus'])
    if st.button("Actualizar datos"):
        st.cache_data.clear()
        st.rerun()

filtros = {
    "busqueda": busqueda or None, "empresa_id": empresa_id,
    "punto_venta_id": puntos_map.get(punto_label), "asesor_id": asesores_map.get(asesor_label),
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
st.caption(f"{len(df)} leads encontrados · ordenados por prioridad, urgencia y fecha de registro.")
if df.empty:
    st.info("No hay leads para los filtros seleccionados.")
    st.stop()

df['puntaje_prioridad'] = df['puntaje_prioridad'].map(lambda value: round(float(value), 2) if pd.notna(value) else None)

def primer_valor(*valores):
    return next((valor for valor in valores if pd.notna(valor) and str(valor).strip()), '—')


df['modelo'] = df.apply(lambda row: primer_valor(row['linea'], row['texto_modelo_original'], row['sku_motocicleta']), axis=1)
df['asesor_mostrar'] = df['asesor'].map(lambda valor: valor if pd.notna(valor) else 'SIN ASIGNAR')
vista = df[['lead_id', 'nombre_cliente', 'empresa', 'punto_venta', 'canal', 'modelo', 'puntaje_prioridad', 'temperatura', 'estado_gestion_normalizado', 'estado_asignacion', 'asesor_mostrar', 'asignado_en', 'registrado_en']].rename(columns={
    'lead_id': 'Lead', 'nombre_cliente': 'Nombre', 'empresa': 'Empresa', 'punto_venta': 'Punto de venta',
    'modelo': 'Modelo / SKU', 'puntaje_prioridad': 'Score / prioridad', 'temperatura': 'Temperatura',
    'estado_gestion_normalizado': 'Estado de gestión', 'estado_asignacion': 'Asignación',
    'asesor_mostrar': 'Asesor asignado', 'asignado_en': 'Fecha asignación', 'registrado_en': 'Fecha de registro',
})
evento = st.dataframe(vista, use_container_width=True, hide_index=True, selection_mode='single-row', on_select='rerun')
seleccion = evento.selection.rows if evento.selection else []
if seleccion:
    st.session_state['lead_id_seleccionado'] = df.iloc[seleccion[0]]['lead_id']
    st.page_link('pages/3_Detalle_Lead.py', label='Ver detalle del lead', icon='🔎')
