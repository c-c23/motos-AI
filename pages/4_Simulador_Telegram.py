"""
pages/4_Simulador_Telegram.py
------------------------------
Fase 1, 2 y 3 — Simulador whatsapp  con extracción e integración de persistencia en PostgreSQL.

- Interfaz conversacional en memoria (session_state).
- Extracción automática de motocicleta, pago inicial, método de pago e intenciones.
- Acción explícita para guardar la conversación y la extracción en PostgreSQL dentro de una transacción atómica.
"""

from datetime import datetime
import streamlit as st

from database import get_connection
from queries.leads_queries import get_catalogo_motocicletas
from services.extraction_service import extract_conversation
from services.persistence_service import guardar_conversacion_simulada
from styles.theme import COLORS, badge_ia, get_global_css, info_field_html

st.set_page_config(
    page_title="Simulador Whatsapp  — Motos AI Leads",
    page_icon="💬",
    layout="wide",
)
st.markdown(get_global_css(), unsafe_allow_html=True)

# ── Catálogo de motocicletas ──────────────────────────────────────────────────
@st.cache_data(ttl=60)
def cargar_catalogo():
    with get_connection() as conn:
        return get_catalogo_motocicletas(conn)


try:
    catalogo = cargar_catalogo()
    catalogo_by_sku = {m["sku"]: m for m in catalogo}
except Exception as e:
    st.error(f"Error cargando catálogo desde PostgreSQL: {e}")
    st.stop()

# ── Inicializar estado ────────────────────────────────────────────────────────
if "sim_mensajes" not in st.session_state:
    st.session_state["sim_mensajes"] = []

if "ultimo_guardado" not in st.session_state:
    st.session_state["ultimo_guardado"] = None

# ── Encabezado ────────────────────────────────────────────────────────────────
st.markdown(
    f"<h1 style='margin-bottom:2px;'>Simulador de conversación</h1>"
    f"<div style='font-size:0.82rem;color:{COLORS['text_muted']};margin-bottom:1.25rem;'>"
    f"Prueba el pipeline de ingesta, extracción IA y scoring con una conversación simulada</div>",
    unsafe_allow_html=True,
)

# Metadatos del canal
st.markdown(
    f"<div style='background:{COLORS['bg_card']};border:1px solid {COLORS['border']};"
    f"border-radius:8px;padding:10px 18px;display:flex;gap:24px;margin-bottom:1.25rem;'>"
    f"<span style='font-size:0.8rem;color:{COLORS['text_muted']};'>"
    f"Canal: <b style='color:{COLORS['text_main']};'>Whatsapp</b></span>"
    f"<span style='font-size:0.8rem;color:{COLORS['text_muted']};'>"
    f"Empresa: <b style='color:{COLORS['text_main']};'>Motos Andinas</b></span>"
    f"<span style='font-size:0.8rem;color:{COLORS['text_muted']};'>"
    f"Punto de venta: <b style='color:{COLORS['text_main']};'>Motos Andinas Armenia</b></span>"
    f"</div>",
    unsafe_allow_html=True,
)

# ── Respuestas automáticas del bot (reglas simples — sin modificar) ───────────
def respuesta_bot(texto: str) -> str:
    """
    Genera una respuesta automática basada en reglas simples.
    """
    t = texto.lower().strip()

    if any(w in t for w in ["hola", "buenas", "buenos días", "buenas tardes"]):
        return "¡Hola! Bienvenido a Motos Andinas. ¿En qué podemos ayudarte hoy?"

    if any(w in t for w in ["moto", "motocicleta", "modelo", "interesado", "interesada"]):
        return "Claro. ¿Qué modelo de motocicleta te interesa?"

    if any(w in t for w in ["apache", "nkd", "boxer", "pulsar", "yamaha", "honda", "suzuki", "tvs"]):
        return "Excelente elección. ¿La compra sería de contado o mediante financiación?"

    if any(w in t for w in ["financiar", "financiación", "crédito", "cuotas", "inicial", "millones"]):
        return (
            "Perfecto. Con esa inicial podemos revisar las opciones de financiación disponibles. "
            "¿Deseas que te enviemos una cotización formal?"
        )

    if any(w in t for w in ["cotización", "cotizar", "precio", "valor", "costo"]):
        return "Con gusto. Un asesor se comunicará contigo para enviarte la cotización detallada."

    if any(w in t for w in ["cita", "visita", "ir", "concesionario", "agencia"]):
        return (
            "Puedes visitarnos en nuestra sede de Armenia de lunes a sábado de 8am a 6pm. "
            "¿Quieres que te agendemos una cita con un asesor?"
        )

    if any(w in t for w in ["gracias", "listo", "ok", "perfecto", "bien"]):
        return "Con gusto. Quedo atento a cualquier otra consulta."

    return "Entendido. ¿Puedes contarme un poco más para poder ayudarte mejor?"


# ── Layout principal: chat (izquierda) + panel IA (derecha) ──────────────────
mensajes = st.session_state["sim_mensajes"]

col_chat, col_ia = st.columns([3, 2], gap="large")

# ── Panel izquierdo: Conversación ─────────────────────────────────────────────
with col_chat:
    st.markdown(
        f"<div style='font-size:0.72rem;font-weight:600;text-transform:uppercase;"
        f"letter-spacing:0.05em;color:{COLORS['text_muted']};margin-bottom:0.75rem;'>"
        f"Conversación</div>",
        unsafe_allow_html=True,
    )

    if not mensajes:
        st.markdown(
            f"<div style='color:{COLORS['text_light']};font-size:0.85rem;padding:12px 0;'>"
            f"La conversación aparecerá aquí. Escribe un mensaje para comenzar.</div>",
            unsafe_allow_html=True,
        )

    for msg in mensajes:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            st.caption(msg["hora"])

    # Input de chat
    texto_usuario = st.chat_input("Escribe un mensaje...")

    if texto_usuario and texto_usuario.strip():
        hora_ahora = datetime.now().strftime("%H:%M")

        st.session_state["sim_mensajes"].append({
            "role":    "user",
            "content": texto_usuario.strip(),
            "hora":    hora_ahora,
        })

        respuesta = respuesta_bot(texto_usuario)
        st.session_state["sim_mensajes"].append({
            "role":    "assistant",
            "content": respuesta,
            "hora":    hora_ahora,
        })

        st.rerun()

    # Acciones
    if mensajes:
        st.markdown("<div style='margin-top:0.75rem;'></div>", unsafe_allow_html=True)
        col_acc1, col_acc2 = st.columns(2)

        with col_acc1:
            if st.button("💾 Guardar en PostgreSQL", type="primary", use_container_width=True):
                tiene_msg_user = any(m.get("role") in ("user", "cliente") for m in mensajes)
                if not tiene_msg_user:
                    st.warning("Se requiere al menos un mensaje del cliente para guardar.")
                else:
                    try:
                        res_persistencia = guardar_conversacion_simulada(
                            messages=mensajes,
                            catalogo=catalogo,
                            nombre_cliente="Cliente Whatsapp Simulado",
                            empresa_id="EMP-01",
                            punto_venta_id="PV-002",
                        )
                        st.session_state["ultimo_guardado"] = res_persistencia
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar conversación en PostgreSQL: {e}")

        with col_acc2:
            if st.button("Limpiar conversación", type="secondary", use_container_width=True):
                st.session_state["sim_mensajes"] = []
                st.session_state["ultimo_guardado"] = None
                st.rerun()

    # Notificación de guardado exitoso
    if st.session_state.get("ultimo_guardado"):
        info_g = st.session_state["ultimo_guardado"]
        sc = info_g.get("scoring", {})
        st.markdown("<div style='margin-top:0.75rem;'></div>", unsafe_allow_html=True)
        st.success(
            f"✅ **Conversación guardada exitosamente.**\n\n"
            f"Lead ID: `{info_g['lead_id']}` &nbsp;·&nbsp; "
            f"Conversación: `{info_g['conversacion_id']}`"
            + (
                f"\n\nScore: `{sc.get('puntaje_prioridad', '—')}` &nbsp;·&nbsp; "
                f"Temperatura: `{sc.get('temperatura', '—')}`"
                if sc else ""
            )
        )

# ── Panel derecho: Información detectada por IA ────────────────────────────────
with col_ia:
    st.markdown(
        f"""<div style="margin-bottom:0.75rem;display:flex;align-items:center;gap:8px;">
        <div style="font-size:0.72rem;font-weight:600;text-transform:uppercase;
                    letter-spacing:0.05em;color:{COLORS['text_muted']};">
            Información detectada</div>
        {badge_ia()}
        </div>""",
        unsafe_allow_html=True,
    )

    if mensajes:
        extraccion = extract_conversation(mensajes, catalogo)
        sku_detectado  = extraccion.get("sku_motocicleta")
        pago_detectado = extraccion.get("pago_inicial")
        metodo_pago    = extraccion.get("metodo_pago")
        intencion      = extraccion.get("intencion_declarada")
        solicita_cot   = extraccion.get("solicita_cotizacion")
        solicita_cit   = extraccion.get("solicita_cita")

        if sku_detectado and sku_detectado in catalogo_by_sku:
            moto_info   = catalogo_by_sku[sku_detectado]
            nombre_moto = f"{moto_info['marca']} {moto_info['linea']}"
        else:
            nombre_moto = None

        # Función helper para mostrar campo con indicador de detección
        def campo_ia(label: str, valor, detected: bool = True) -> str:
            if valor is None or valor == "" or valor is False and label.lower() not in ("solicita cotización", "solicita cita"):
                return (
                    f"<div style='margin-bottom:10px;'>"
                    f"<div style='font-size:0.68rem;font-weight:600;text-transform:uppercase;"
                    f"letter-spacing:0.05em;color:{COLORS['text_light']};margin-bottom:2px;'>{label}</div>"
                    f"<div style='font-size:0.875rem;color:{COLORS['text_light']};'>—</div>"
                    f"</div>"
                )
            v_str = str(valor)
            if isinstance(valor, bool):
                v_str = "Sí" if valor else "No"
            return (
                f"<div style='margin-bottom:10px;'>"
                f"<div style='font-size:0.68rem;font-weight:600;text-transform:uppercase;"
                f"letter-spacing:0.05em;color:{COLORS['text_muted']};margin-bottom:2px;'>{label}</div>"
                f"<div style='font-size:0.875rem;font-weight:500;color:{COLORS['text_main']};'>{v_str}</div>"
                f"</div>"
            )

        pago_str = f"${int(pago_detectado):,}".replace(",", ".") if pago_detectado else None

        st.markdown(
            f"<div style='background:{COLORS['ia_bg']};border:1px solid #C7D2FE;"
            f"border-radius:8px;padding:16px 20px;'>",
            unsafe_allow_html=True,
        )
        st.markdown(campo_ia("Motocicleta", nombre_moto), unsafe_allow_html=True)
        st.markdown(campo_ia("SKU", sku_detectado), unsafe_allow_html=True)
        st.markdown(campo_ia("Pago inicial", pago_str), unsafe_allow_html=True)
        st.markdown(campo_ia("Método de pago", metodo_pago), unsafe_allow_html=True)
        st.markdown(campo_ia("Intención", intencion), unsafe_allow_html=True)
        st.markdown(campo_ia("Solicita cotización", solicita_cot), unsafe_allow_html=True)
        st.markdown(campo_ia("Solicita cita", solicita_cit), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    else:
        st.markdown(
            f"<div style='background:{COLORS['bg_card']};border:1px solid {COLORS['border']};"
            f"border-radius:8px;padding:16px 20px;'>",
            unsafe_allow_html=True,
        )
        campos_vacios = ["Motocicleta", "SKU", "Pago inicial", "Método de pago",
                         "Intención", "Solicita cotización", "Solicita cita"]
        for campo in campos_vacios:
            st.markdown(info_field_html(campo, "—"), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            f"<div style='font-size:0.78rem;color:{COLORS['text_light']};margin-top:8px;'>"
            f"Los campos se completarán automáticamente mientras converses.</div>",
            unsafe_allow_html=True,
        )
