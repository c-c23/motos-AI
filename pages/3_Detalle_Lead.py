"""
pages/3_Detalle_Lead.py
------------------------
Ficha completa de un lead seleccionado.
Lee el lead_id desde st.session_state["lead_id_seleccionado"].
Muestra: información del cliente, datos comerciales, scoring IA,
asignación, conversación (mensajes) e historial de eventos.
"""

import json
import streamlit as st
from database import get_connection
from queries.leads_queries import (
    get_lead_by_id,
    get_mensajes_lead,
    get_eventos_lead,
    get_extracciones_lead,
    get_puntaje_lead,
)

st.set_page_config(
    page_title="Detalle Lead — Motos AI Leads",
    page_icon="🔍",
    layout="wide",
)

st.title("🔍 Detalle del lead")

# ──────────────────────────────────────────────
# Verificar que hay un lead seleccionado
# ──────────────────────────────────────────────
lead_id = st.session_state.get("lead_id_seleccionado")

if not lead_id:
    st.warning("Ningún lead seleccionado. Ve a la **Bandeja de leads** y selecciona uno.")
    st.page_link("pages/2_Leads.py", label="Ir a la bandeja de leads →", icon="📋")
    st.stop()

# ──────────────────────────────────────────────
# Carga de datos del lead
# ──────────────────────────────────────────────
@st.cache_data(ttl=30)
def cargar_lead(lid):
    with get_connection() as conn:
        lead      = get_lead_by_id(conn, lid)
        mensajes  = get_mensajes_lead(conn, lid)
        eventos   = get_eventos_lead(conn, lid)
        extraccion = get_extracciones_lead(conn, lid)
        puntaje   = get_puntaje_lead(conn, lid)
    return lead, mensajes, eventos, extraccion, puntaje


try:
    lead, mensajes, eventos, extraccion, puntaje = cargar_lead(lead_id)
except Exception as e:
    st.error(f"Error cargando datos del lead: {e}")
    st.stop()

if not lead:
    st.error(f"Lead {lead_id} no encontrado en la base de datos.")
    st.stop()

# ──────────────────────────────────────────────
# Encabezado del lead
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


temp_badge = badge_temperatura(lead.get("temperatura"))
prioridad = lead.get("puntaje_prioridad")
prioridad_str = f"{float(prioridad):.2f}" if prioridad is not None else "—"

st.subheader(f"{lead['nombre_cliente']}  ·  {lead_id}")
col_h1, col_h2, col_h3 = st.columns(3)
col_h1.metric("Temperatura", temp_badge)
col_h2.metric("Prioridad Operacional", prioridad_str)
col_h3.metric("Estado", lead.get("estado_gestion", "—"))

st.divider()

# ──────────────────────────────────────────────
# Sección 1: Información del cliente
# ──────────────────────────────────────────────
with st.expander("👤 Información del cliente", expanded=True):
    c1, c2, c3 = st.columns(3)
    c1.write(f"**Nombre:** {lead.get('nombre_cliente', '—')}")
    c1.write(f"**Teléfono:** {lead.get('telefono', '—')}")
    c1.write(f"**Correo:** {lead.get('correo') or '—'}")
    c2.write(f"**Ciudad:** {lead.get('ciudad') or '—'}")
    c2.write(f"**Canal:** {lead.get('canal', '—')}")
    c3.write(f"**Campaña:** {lead.get('campana') or '—'}")
    c3.write(f"**Registrado:** {lead.get('registrado_en', '—')}")

# ──────────────────────────────────────────────
# Sección 2: Información comercial
# ──────────────────────────────────────────────
with st.expander("💼 Información comercial", expanded=True):
    c1, c2, c3 = st.columns(3)

    moto_str = "—"
    if lead.get("marca") and lead.get("linea"):
        moto_str = f"{lead['marca']} {lead['linea']}"
        if lead.get("cilindraje_cc"):
            moto_str += f" {lead['cilindraje_cc']}cc"
    c1.write(f"**Moto de interés:** {moto_str}")
    c1.write(f"**SKU:** {lead.get('sku_motocicleta') or '—'}")
    c1.write(f"**Segmento:** {lead.get('segmento') or '—'}")

    precio = lead.get("precio_lista")
    precio_str = f"${int(precio):,}".replace(",", ".") if precio else "—"
    pago_ini = lead.get("pago_inicial")
    pago_str = f"${int(pago_ini):,}".replace(",", ".") if pago_ini else "—"
    c2.write(f"**Precio lista:** {precio_str}")
    c2.write(f"**Pago inicial:** {pago_str}")
    c2.write(f"**Método de pago:** {lead.get('metodo_pago') or '—'}")

    c3.write(f"**Intención:** {lead.get('intencion_declarada') or '—'}")
    c3.write(f"**Solicita cotización:** {'Sí' if lead.get('solicita_cotizacion') else 'No'}")
    c3.write(f"**Solicita cita:** {'Sí' if lead.get('solicita_cita') else 'No'}")
    if lead.get("objecion_principal"):
        st.write(f"**Objeción principal:** {lead['objecion_principal']}")

# ──────────────────────────────────────────────
# Sección 3: IA / Scoring V1
# ──────────────────────────────────────────────
with st.expander("🤖 IA / Scoring Operacional", expanded=True):
    c1, c2, c3 = st.columns(3)
    c1.metric("Puntaje de prioridad", prioridad_str)
    c2.metric("Temperatura", temp_badge)
    c3.metric("Modelo de scoring", puntaje.get("modelo_scoring", "—") if puntaje else "—")

    if puntaje and puntaje.get("razones"):
        st.markdown("**Razones del score:**")
        razones = puntaje["razones"]
        if isinstance(razones, str):
            razones = json.loads(razones)

        if isinstance(razones, dict) and "tiempo" in razones:
            t_info = razones.get("tiempo", {})
            horas_v = t_info.get("horas", 0)
            st.write(f"• Lead sin contacto durante **{horas_v} horas** (intervalo: `{t_info.get('bucket', '—')}`)")

            cita_info = razones.get("pidio_cita", {})
            if cita_info.get("valor"):
                st.write("• **Solicitó cita**")
            else:
                st.write("• No solicitó cita")

            cuota_info = razones.get("manifesto_cuota_inicial", {})
            if cuota_info.get("valor"):
                st.write("• **Manifestó cuota inicial**")
            else:
                st.write("• No manifestó cuota inicial")
        else:
            for k, v in razones.items():
                st.write(f"  • **{k.replace('_', ' ').capitalize()}:** {v}")

    if puntaje:
        st.caption(
            f"Modelo: `{puntaje.get('modelo_scoring', '—')}` · "
            f"Versión: `{puntaje.get('version_scoring', '—')}` · "
            f"Puntuado: {puntaje.get('puntuado_en', '—')}"
        )

# ──────────────────────────────────────────────
# Sección 4: Asignación
# ──────────────────────────────────────────────
with st.expander("📌 Asignación", expanded=True):
    c1, c2, c3 = st.columns(3)
    c1.write(f"**Empresa:** {lead.get('empresa') or '—'}")
    c1.write(f"**Punto de venta:** {lead.get('punto_venta') or '—'}")
    c2.write(f"**Asesor asignado:** {lead.get('asesor') or 'Sin asignar'}")
    c2.write(f"**ID Asesor:** {lead.get('asesor_id') or '—'}")
    c3.write(f"**Primer contacto:** {lead.get('primer_contacto_en') or '—'}")

# ──────────────────────────────────────────────
# Sección 5: Conversación (mensajes)
# ──────────────────────────────────────────────
with st.expander("💬 Conversación", expanded=True):
    if not mensajes:
        st.info("No hay mensajes registrados para este lead.")
    else:
        for msg in mensajes:
            remitente = msg.get("remitente", "—")
            texto = msg.get("texto", "")
            hora = msg.get("enviado_en")
            hora_str = hora.strftime("%H:%M") if hora else ""

            if remitente.lower() == "cliente":
                with st.chat_message("user"):
                    st.write(texto)
                    if hora_str:
                        st.caption(hora_str)
            else:
                with st.chat_message("assistant"):
                    st.write(f"**{remitente}:** {texto}")
                    if hora_str:
                        st.caption(hora_str)

# ──────────────────────────────────────────────
# Sección 6: Historial de eventos
# ──────────────────────────────────────────────
with st.expander("📅 Historial de eventos", expanded=False):
    if not eventos:
        st.info("No hay eventos registrados para este lead.")
    else:
        for ev in eventos:
            fecha = ev.get("fecha_evento")
            fecha_str = fecha.strftime("%Y-%m-%d %H:%M") if fecha else "—"
            tipo = ev.get("tipo_evento", "—")
            asesor_ev = ev.get("asesor") or ""
            metadatos = ev.get("metadatos") or {}
            if isinstance(metadatos, str):
                metadatos = json.loads(metadatos)

            with st.container():
                col_f, col_d = st.columns([1, 4])
                col_f.caption(fecha_str)
                detalle = f"**{tipo}**"
                if asesor_ev:
                    detalle += f" · {asesor_ev}"
                if metadatos:
                    extras = []
                    if metadatos.get("temperatura"):
                        extras.append(f"Temperatura: {metadatos['temperatura']}")
                    if metadatos.get("puntaje_prioridad"):
                        extras.append(f"Prioridad: {metadatos['puntaje_prioridad']}")
                    if extras:
                        detalle += " · " + " · ".join(extras)
                col_d.write(detalle)
