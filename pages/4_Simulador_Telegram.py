"""
pages/4_Simulador_Telegram.py
------------------------------
Fase 1, 2 y 3 — Simulador Telegram con extracción e integración de persistencia en PostgreSQL.

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

st.set_page_config(
    page_title="Simulador Telegram — Motos AI Leads",
    page_icon="💬",
    layout="centered",
)

# ──────────────────────────────────────────────
# Cargar catálogo de motocicletas (caché de 60s)
# ──────────────────────────────────────────────
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

# ──────────────────────────────────────────────
# Inicializar estado de la conversación y guardado
# ──────────────────────────────────────────────
if "sim_mensajes" not in st.session_state:
    st.session_state["sim_mensajes"] = []

if "ultimo_guardado" not in st.session_state:
    st.session_state["ultimo_guardado"] = None

# ──────────────────────────────────────────────
# Encabezado — información del canal simulado
# ──────────────────────────────────────────────
st.title("💬 Simulador de conversación")

col1, col2, col3 = st.columns(3)
col1.markdown("**Canal:** Telegram")
col2.markdown("**Empresa:** Motos Andinas")
col3.markdown("**Punto de venta:** Motos Andinas Armenia")

st.divider()

# ──────────────────────────────────────────────
# Respuestas automáticas del bot (reglas simples)
# ──────────────────────────────────────────────
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

    # Respuesta genérica
    return "Entendido. ¿Puedes contarme un poco más para poder ayudarte mejor?"


# ──────────────────────────────────────────────
# Mostrar conversación existente
# ──────────────────────────────────────────────
mensajes = st.session_state["sim_mensajes"]

if not mensajes:
    st.caption("La conversación aparecerá aquí. Escribe un mensaje para comenzar.")

for msg in mensajes:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        st.caption(msg["hora"])

# ──────────────────────────────────────────────
# Seccion: Información detectada en tiempo real
# ──────────────────────────────────────────────
st.divider()

st.subheader("🔍 Información detectada")

if mensajes:
    extraccion = extract_conversation(mensajes, catalogo)
    sku_detectado = extraccion.get("sku_motocicleta")
    pago_detectado = extraccion.get("pago_inicial")
    metodo_pago = extraccion.get("metodo_pago")
    intencion = extraccion.get("intencion_declarada")
    solicita_cot = extraccion.get("solicita_cotizacion")
    solicita_cit = extraccion.get("solicita_cita")

    # Fila 1: Motocicleta, SKU, Pago inicial
    col1, col2, col3 = st.columns(3)
    if sku_detectado and sku_detectado in catalogo_by_sku:
        moto_info = catalogo_by_sku[sku_detectado]
        nombre_moto = f"{moto_info['marca']} {moto_info['linea']}"
        col1.metric("Motocicleta", nombre_moto)
        col2.metric("SKU", sku_detectado)
    else:
        col1.metric("Motocicleta", "No detectada")
        col2.metric("SKU", "—")

    if pago_detectado:
        pago_str = f"${pago_detectado:,}".replace(",", ".")
        col3.metric("Pago inicial", pago_str)
    else:
        col3.metric("Pago inicial", "—")

    # Fila 2: Método de pago, Intención, Cotización, Cita
    col4, col5, col6, col7 = st.columns(4)
    col4.metric("Método de pago", metodo_pago or "—")
    col5.metric("Intención", intencion or "—")
    col6.metric("Solicita cotización", "Sí" if solicita_cot else "No")
    col7.metric("Solicita cita", "Sí" if solicita_cit else "No")
else:
    col1, col2, col3 = st.columns(3)
    col1.metric("Motocicleta", "—")
    col2.metric("SKU", "—")
    col3.metric("Pago inicial", "—")

    col4, col5, col6, col7 = st.columns(4)
    col4.metric("Método de pago", "—")
    col5.metric("Intención", "—")
    col6.metric("Solicita cotización", "—")
    col7.metric("Solicita cita", "—")

st.divider()

# ──────────────────────────────────────────────
# Input del usuario
# ──────────────────────────────────────────────
texto_usuario = st.chat_input("Escribe un mensaje...")

if texto_usuario and texto_usuario.strip():
    hora_ahora = datetime.now().strftime("%H:%M")

    # Registrar mensaje del cliente
    st.session_state["sim_mensajes"].append({
        "role":    "user",
        "content": texto_usuario.strip(),
        "hora":    hora_ahora,
    })

    # Generar y registrar respuesta del bot
    respuesta = respuesta_bot(texto_usuario)
    st.session_state["sim_mensajes"].append({
        "role":    "assistant",
        "content": respuesta,
        "hora":    hora_ahora,
    })

    st.rerun()

# ──────────────────────────────────────────────
# Acciones: Guardar conversación y Limpiar
# ──────────────────────────────────────────────
if mensajes:
    col_acc1, col_acc2 = st.columns(2)

    with col_acc1:
        if st.button("💾 Guardar conversación en PostgreSQL", type="primary", use_container_width=True):
            tiene_msg_user = any(m.get("role") in ("user", "cliente") for m in mensajes)
            if not tiene_msg_user:
                st.warning("Se requiere al menos un mensaje del cliente para guardar.")
            else:
                try:
                    res_persistencia = guardar_conversacion_simulada(
                        messages=mensajes,
                        catalogo=catalogo,
                        nombre_cliente="Cliente Telegram Simulado",
                        empresa_id="EMP-01",
                        punto_venta_id="PV-002",
                    )
                    st.session_state["ultimo_guardado"] = res_persistencia
                    # Limpiar caché de Streamlit para actualizar Dashboard/Leads
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar conversación en PostgreSQL: {e}")

    with col_acc2:
        if st.button("Limpiar conversación", type="secondary", use_container_width=True):
            st.session_state["sim_mensajes"] = []
            st.session_state["ultimo_guardado"] = None
            st.rerun()

# ──────────────────────────────────────────────
# Notificación de guardado exitoso
# ──────────────────────────────────────────────
if st.session_state.get("ultimo_guardado"):
    info_g = st.session_state["ultimo_guardado"]
    sc = info_g.get("scoring", {})
    score_str = f"• **Puntaje de Prioridad V1:** `{sc.get('puntaje_prioridad', '—')}` | **Temperatura:** `{sc.get('temperatura', '—')}`\n" if sc else ""
    st.success(
        f"✅ **Conversación guardada exitosamente en PostgreSQL.**\n\n"
        f"• **Lead ID:** `{info_g['lead_id']}`\n"
        f"• **Conversación ID:** `{info_g['conversacion_id']}`\n"
        f"{score_str}\n"
        f"Puedes consultar este nuevo lead en el **Dashboard** o la **Bandeja de Leads**."
    )
