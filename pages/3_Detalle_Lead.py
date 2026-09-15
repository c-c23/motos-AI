"""
pages/3_Detalle_Lead.py
------------------------
Ficha completa de un lead seleccionado — vista CRM.
Lee el lead_id desde st.session_state["lead_id_seleccionado"].
Muestra: información del cliente, datos comerciales, scoring IA,
asignación, conversación (mensajes) e historial de eventos.
"""

import json
import streamlit as st
from database import get_connection
from queries.leads_queries import (
    factores_score_desde_db,
    get_lead_by_id,
    get_mensajes_lead,
    get_eventos_lead,
    get_extracciones_lead,
    get_puntaje_lead,
)
from styles.theme import (
    COLORS, badge_temperatura, badge_asignacion, badge_ia,
    get_global_css, section_header_html, info_field_html,
)

st.set_page_config(
    page_title="Detalle Lead — Motos AI Leads",
    page_icon="🔍",
    layout="wide",
)
st.markdown(get_global_css(), unsafe_allow_html=True)

# ── Verificar que hay un lead seleccionado ────────────────────────────────────
lead_id = st.session_state.get("lead_id_seleccionado")

if not lead_id:
    st.markdown("<div style='margin-top:2rem;'></div>", unsafe_allow_html=True)
    st.warning("Ningún lead seleccionado. Ve a la **Bandeja de leads** y selecciona uno.")
    st.page_link("pages/2_Leads.py", label="← Ir a la bandeja de leads")
    st.stop()

# ── Carga de datos del lead ───────────────────────────────────────────────────
@st.cache_data(ttl=30)
def cargar_lead(lid):
    with get_connection() as conn:
        lead       = get_lead_by_id(conn, lid)
        mensajes   = get_mensajes_lead(conn, lid)
        eventos    = get_eventos_lead(conn, lid)
        extraccion = get_extracciones_lead(conn, lid)
        puntaje    = get_puntaje_lead(conn, lid)
    return lead, mensajes, eventos, extraccion, puntaje


try:
    lead, mensajes, eventos, extraccion, puntaje = cargar_lead(lead_id)
except Exception as e:
    st.error(f"Error cargando datos del lead: {e}")
    st.stop()

if not lead:
    st.error(f"Lead {lead_id} no encontrado en la base de datos.")
    st.stop()

# ── helpers locales ───────────────────────────────────────────────────────────
def val(campo: str, default: str = "—") -> str:
    """Devuelve el valor del lead como string o el default."""
    v = lead.get(campo)
    if v is None or str(v).strip() == "":
        return default
    return str(v)


def fmt_precio(campo: str) -> str:
    precio = lead.get(campo)
    if precio:
        try:
            return f"${int(precio):,}".replace(",", ".")
        except Exception:
            return str(precio)
    return "—"


def fmt_ia(valor) -> str:
    if valor is None:
        return "—"
    if valor is True:
        return "Sí"
    if valor is False:
        return "No"
    return str(valor)


prioridad = lead.get("puntaje_prioridad")
prioridad_str = f"{float(prioridad):.2f}" if prioridad is not None else "—"
temperatura = lead.get("temperatura")

# ── Navegación de regreso ─────────────────────────────────────────────────────
st.page_link("pages/2_Leads.py", label="← Volver a la bandeja")

# ── Encabezado de la ficha ────────────────────────────────────────────────────
st.markdown("<div style='margin-top:0.5rem;'></div>", unsafe_allow_html=True)

nombre = lead.get("nombre_cliente", "Cliente sin nombre")
estado_gestion = val("estado_gestion_normalizado")

badge_temp_html = badge_temperatura(temperatura)
badge_estado_asig_html = badge_asignacion(lead.get("estado_asignacion"))

# Determinar color de borde según temperatura
borde_temp = {
    "Crítico": COLORS["critico_dot"],
    "Alto":    COLORS["alto_dot"],
    "Medio":   COLORS["medio_dot"],
    "Bajo":    COLORS["bajo_dot"],
}.get(temperatura, COLORS["border"])

st.markdown(
    f"""<div style="background:{COLORS['bg_card']};border:1px solid {COLORS['border']};
    border-left:5px solid {borde_temp};border-radius:10px;
    padding:18px 24px;margin-bottom:1.25rem;">
    <div style="font-size:0.72rem;font-weight:600;text-transform:uppercase;
                letter-spacing:0.05em;color:{COLORS['text_muted']};margin-bottom:4px;">
        Lead &nbsp;·&nbsp; {lead_id}
    </div>
    <div style="font-size:1.4rem;font-weight:700;color:{COLORS['text_main']};
                margin-bottom:10px;line-height:1.2;">{nombre}</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
        {badge_temp_html}
        {badge_estado_asig_html}
        <span style="font-size:0.72rem;color:{COLORS['text_muted']};">
            Score: <b style="color:{COLORS['text_main']};">{prioridad_str}</b>
        </span>
        <span style="font-size:0.72rem;color:{COLORS['text_muted']};">
            Estado: <b style="color:{COLORS['text_main']};">{estado_gestion}</b>
        </span>
    </div>
    </div>""",
    unsafe_allow_html=True,
)

# ── Sección: Cliente + Comercial en dos columnas ─────────────────────────────
st.markdown(section_header_html("Información del lead"), unsafe_allow_html=True)

col_cliente, col_comercial = st.columns(2)

with col_cliente:
    st.markdown(
        f"<div style='background:{COLORS['bg_card']};border:1px solid {COLORS['border']};"
        f"border-radius:8px;padding:16px 20px;'>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div style='font-size:0.68rem;font-weight:600;text-transform:uppercase;"
        f"letter-spacing:0.05em;color:{COLORS['text_muted']};margin-bottom:12px;'>"
        f"👤 Cliente</div>",
        unsafe_allow_html=True,
    )
    st.markdown(info_field_html("Nombre", val("nombre_cliente")), unsafe_allow_html=True)
    st.markdown(info_field_html("Teléfono", val("telefono")), unsafe_allow_html=True)
    st.markdown(info_field_html("Correo", val("correo")), unsafe_allow_html=True)
    st.markdown(info_field_html("Ciudad", val("ciudad")), unsafe_allow_html=True)
    st.markdown(info_field_html("Canal", val("canal")), unsafe_allow_html=True)
    st.markdown(info_field_html("Campaña", val("campana")), unsafe_allow_html=True)
    st.markdown(info_field_html("Registrado", val("registrado_en")), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with col_comercial:
    st.markdown(
        f"<div style='background:{COLORS['bg_card']};border:1px solid {COLORS['border']};"
        f"border-radius:8px;padding:16px 20px;'>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div style='font-size:0.68rem;font-weight:600;text-transform:uppercase;"
        f"letter-spacing:0.05em;color:{COLORS['text_muted']};margin-bottom:12px;'>"
        f"💼 Interés comercial</div>",
        unsafe_allow_html=True,
    )
    # Construir descripción de moto
    marca = lead.get("marca")
    linea = lead.get("linea")
    cc = lead.get("cilindraje_cc")
    if marca and linea:
        moto_str = f"{marca} {linea}"
        if cc:
            moto_str += f" {cc}cc"
    else:
        moto_str = "—"

    st.markdown(info_field_html("Moto de interés", moto_str), unsafe_allow_html=True)
    st.markdown(info_field_html("SKU", val("sku_motocicleta")), unsafe_allow_html=True)
    st.markdown(info_field_html("Segmento", val("segmento")), unsafe_allow_html=True)
    st.markdown(info_field_html("Precio lista", fmt_precio("precio_lista")), unsafe_allow_html=True)
    st.markdown(info_field_html("Empresa", val("empresa")), unsafe_allow_html=True)
    st.markdown(info_field_html("Punto de venta", val("punto_venta")), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ── Sección: Asignación ───────────────────────────────────────────────────────
st.markdown("<div style='margin-top:0.5rem;'></div>", unsafe_allow_html=True)
st.markdown(section_header_html("Asignación"), unsafe_allow_html=True)

asesor_nombre = lead.get("asesor") or "Sin asignar"
asesor_id_val = val("asesor_id")
fecha_asig = val("asignado_en")
primer_contacto = val("primer_contacto_en")

col_a1, col_a2, col_a3 = st.columns(3)
with col_a1:
    st.markdown(
        f"<div style='background:{COLORS['bg_card']};border:1px solid {COLORS['border']};"
        f"border-radius:8px;padding:14px 18px;'>",
        unsafe_allow_html=True,
    )
    st.markdown(info_field_html("Empresa", val("empresa")), unsafe_allow_html=True)
    st.markdown(info_field_html("Punto de venta", val("punto_venta")), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with col_a2:
    st.markdown(
        f"<div style='background:{COLORS['bg_card']};border:1px solid {COLORS['border']};"
        f"border-radius:8px;padding:14px 18px;'>",
        unsafe_allow_html=True,
    )
    st.markdown(info_field_html("Asesor asignado", asesor_nombre), unsafe_allow_html=True)
    st.markdown(info_field_html("ID Asesor", asesor_id_val), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with col_a3:
    st.markdown(
        f"<div style='background:{COLORS['bg_card']};border:1px solid {COLORS['border']};"
        f"border-radius:8px;padding:14px 18px;'>",
        unsafe_allow_html=True,
    )
    st.markdown(info_field_html("Fecha de asignación", fecha_asig), unsafe_allow_html=True)
    st.markdown(info_field_html("Primer contacto", primer_contacto), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ── Sección: Extracción IA ────────────────────────────────────────────────────
st.markdown("<div style='margin-top:0.5rem;'></div>", unsafe_allow_html=True)
st.markdown(
    f"""<div style="margin: 1.5rem 0 0.75rem 0;">
    <div style="display:flex;align-items:center;gap:8px;font-size:0.72rem;font-weight:600;
                text-transform:uppercase;letter-spacing:0.07em;color:{COLORS['text_muted']};
                border-bottom:2px solid {COLORS['border']};padding-bottom:6px;">
        Extracción automática &nbsp;{badge_ia()}
    </div>
    </div>""",
    unsafe_allow_html=True,
)

if not extraccion:
    st.markdown(
        f"<div style='background:{COLORS['bg_card']};border:1px solid {COLORS['border']};"
        f"border-radius:8px;padding:14px 18px;color:{COLORS['text_muted']};font-size:0.875rem;'>"
        f"No existe extracción IA para este lead.</div>",
        unsafe_allow_html=True,
    )
else:
    col_ia1, col_ia2, col_ia3 = st.columns(3)
    pago = extraccion.get('pago_inicial')
    pago_str = f"${int(pago):,}".replace(",", ".") if pago is not None else "—"

    with col_ia1:
        st.markdown(
            f"<div style='background:{COLORS['ia_bg']};border:1px solid #C7D2FE;"
            f"border-radius:8px;padding:14px 18px;'>",
            unsafe_allow_html=True,
        )
        st.markdown(info_field_html("Pago inicial", pago_str), unsafe_allow_html=True)
        st.markdown(info_field_html("Método de pago", fmt_ia(extraccion.get('metodo_pago'))), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_ia2:
        st.markdown(
            f"<div style='background:{COLORS['ia_bg']};border:1px solid #C7D2FE;"
            f"border-radius:8px;padding:14px 18px;'>",
            unsafe_allow_html=True,
        )
        st.markdown(info_field_html("Intención declarada", fmt_ia(extraccion.get('intencion_declarada'))), unsafe_allow_html=True)
        st.markdown(info_field_html("Objeción principal", fmt_ia(extraccion.get('objecion_principal'))), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_ia3:
        st.markdown(
            f"<div style='background:{COLORS['ia_bg']};border:1px solid #C7D2FE;"
            f"border-radius:8px;padding:14px 18px;'>",
            unsafe_allow_html=True,
        )
        st.markdown(info_field_html("Solicita cotización", fmt_ia(extraccion.get('solicita_cotizacion'))), unsafe_allow_html=True)
        st.markdown(info_field_html("Solicita cita", fmt_ia(extraccion.get('solicita_cita'))), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    modelo_ext = extraccion.get('modelo_extraccion') or '—'
    version_ext = extraccion.get('version_extraccion') or '—'
    st.markdown(
        f"<div style='font-size:0.72rem;color:{COLORS['text_light']};margin-top:4px;'>"
        f"Modelo: <code>{modelo_ext}</code> &nbsp;·&nbsp; Versión: <code>{version_ext}</code></div>",
        unsafe_allow_html=True,
    )

# ── Sección: Scoring ─────────────────────────────────────────────────────────
st.markdown("<div style='margin-top:0.5rem;'></div>", unsafe_allow_html=True)
st.markdown(section_header_html("Scoring operacional"), unsafe_allow_html=True)

st.markdown(
    f"<div style='background:{COLORS['bg_card']};border:1px solid {COLORS['border']};"
    f"border-radius:8px;padding:16px 20px;'>",
    unsafe_allow_html=True,
)

col_sc1, col_sc2 = st.columns([1, 2])
with col_sc1:
    st.markdown(info_field_html("Puntaje de prioridad", prioridad_str), unsafe_allow_html=True)
    st.markdown(
        f"<div style='margin-bottom:10px;'>"
        f"<div style='font-size:0.68rem;font-weight:600;text-transform:uppercase;"
        f"letter-spacing:0.05em;color:{COLORS['text_light']};margin-bottom:4px;'>Temperatura</div>"
        f"{badge_temperatura(temperatura)}"
        f"</div>",
        unsafe_allow_html=True,
    )
    if puntaje:
        modelo_sc = puntaje.get('modelo_scoring', '—')
        version_sc = puntaje.get('version_scoring', '—')
        puntuado_en = puntaje.get('puntuado_en', '—')
        st.markdown(info_field_html("Modelo", modelo_sc), unsafe_allow_html=True)
        st.markdown(info_field_html("Versión", str(version_sc)), unsafe_allow_html=True)
        st.markdown(info_field_html("Puntuado", str(puntuado_en)), unsafe_allow_html=True)

with col_sc2:
    if puntaje and puntaje.get("razones"):
        st.markdown(
            f"<div style='font-size:0.68rem;font-weight:600;text-transform:uppercase;"
            f"letter-spacing:0.05em;color:{COLORS['text_muted']};margin-bottom:8px;'>"
            f"Factores del score</div>",
            unsafe_allow_html=True,
        )
        factores = factores_score_desde_db(puntaje["razones"])
        if factores:
            for factor in factores:
                st.markdown(
                    f"<div style='font-size:0.85rem;color:{COLORS['text_main']};padding:4px 0;"
                    f"border-bottom:1px solid {COLORS['border']};'>"
                    f"<span style='color:{COLORS['primary_light']};margin-right:6px;'>›</span>{factor}</div>",
                    unsafe_allow_html=True,
                )
        else:
            razones = puntaje["razones"]
            if isinstance(razones, str):
                try:
                    razones = json.loads(razones)
                except json.JSONDecodeError:
                    pass
            st.json(razones)

st.markdown("</div>", unsafe_allow_html=True)

# ── Sección: Conversación e Historial en Tabs ─────────────────────────────────
st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)
tab_conv, tab_hist = st.tabs(["💬 Conversación", "📅 Historial de eventos"])

with tab_conv:
    if not mensajes:
        st.markdown(
            f"<div style='padding:16px;color:{COLORS['text_muted']};font-size:0.875rem;'>"
            f"No hay conversación registrada.</div>",
            unsafe_allow_html=True,
        )
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

with tab_hist:
    if not eventos:
        st.markdown(
            f"<div style='padding:16px;color:{COLORS['text_muted']};font-size:0.875rem;'>"
            f"No hay eventos registrados para este lead.</div>",
            unsafe_allow_html=True,
        )
    else:
        for ev in eventos:
            fecha = ev.get("fecha_evento")
            fecha_str = fecha.strftime("%Y-%m-%d %H:%M") if fecha else "—"
            tipo = ev.get("tipo_evento", "—")
            asesor_ev = ev.get("asesor") or ""
            metadatos = ev.get("metadatos") or {}
            if isinstance(metadatos, str):
                metadatos = json.loads(metadatos)

            extras = []
            if metadatos.get("temperatura"):
                extras.append(f"Temperatura: {metadatos['temperatura']}")
            if metadatos.get("puntaje_prioridad"):
                extras.append(f"Prioridad: {metadatos['puntaje_prioridad']}")

            detalle_extra = (" &nbsp;·&nbsp; " + " &nbsp;·&nbsp; ".join(extras)) if extras else ""
            asesor_str = (f" &nbsp;·&nbsp; {asesor_ev}") if asesor_ev else ""

            st.markdown(
                f"<div style='display:flex;gap:16px;padding:8px 0;"
                f"border-bottom:1px solid {COLORS['border']};align-items:flex-start;'>",
                unsafe_allow_html=True,
            )
            col_f, col_d = st.columns([1, 4])
            col_f.markdown(
                f"<span style='font-size:0.72rem;color:{COLORS['text_light']};'>{fecha_str}</span>",
                unsafe_allow_html=True,
            )
            col_d.markdown(
                f"<span style='font-size:0.85rem;font-weight:600;color:{COLORS['text_main']};'>{tipo}</span>"
                f"<span style='font-size:0.8rem;color:{COLORS['text_muted']};'>{asesor_str}{detalle_extra}</span>",
                unsafe_allow_html=True,
            )
