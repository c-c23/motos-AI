"""
pages/4_Simulador_Telegram.py
------------------------------
Simulador de conversación de WhatsApp con extracción NLP e integración de persistencia en PostgreSQL.

- Interfaz conversacional en memoria (session_state).
- Extracción automática de motocicleta, pago inicial, método de pago e intenciones.
- Acción explícita para guardar la conversación y la extracción en PostgreSQL dentro de una transacción atómica.
"""

from datetime import datetime
import html
import streamlit as st

from database import get_connection
from queries.leads_queries import get_catalogo_motocicletas
from services.extraction_service import extract_conversation
from services.persistence_service import guardar_conversacion_simulada
from services.conversation_engine import process_turn, EstadoConversacional, build_extraction_view
from styles.theme import COLORS, badge_temperatura, badge_asignacion, get_global_css

# ──────────────────────────────────────────────
# Configuración de página y estilos
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Simulador WhatsApp — Motos AI Leads",
    page_icon="💬",
    layout="wide",
)
st.markdown(get_global_css(), unsafe_allow_html=True)

c = COLORS

# ── CSS específico del Simulador ──────────────────────────────────────────────
st.markdown(
    """
    <style>
      [data-testid="stMainBlockContainer"] { max-width: 1440px; padding-top: 1.6rem; }

      /* ── Hero Banner ── */
      .sim-hero {
        background: linear-gradient(135deg, #0F172A 0%, #064E3B 50%, #0F172A 100%);
        border: 1px solid #134E4A;
        border-radius: 12px;
        padding: 22px 28px;
        margin: .1rem 0 1.35rem;
        box-shadow: 0 8px 24px rgba(6, 78, 59, 0.15);
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 16px;
      }
      .sim-hero-eyebrow {
        font-size: .68rem;
        font-weight: 700;
        letter-spacing: .1em;
        text-transform: uppercase;
        color: #34D399;
        margin-bottom: .45rem;
        display: flex;
        align-items: center;
        gap: 6px;
      }
      .sim-hero-title {
        color: #F8FAFC;
        font-size: 1.45rem;
        font-weight: 800;
        margin: 0 0 .3rem;
        letter-spacing: -.02em;
        line-height: 1.2;
      }
      .sim-hero-sub {
        color: #94A3B8;
        font-size: .82rem;
        line-height: 1.55;
        max-width: 720px;
      }
      .sim-hero-badge {
        background: rgba(16, 185, 129, .15);
        border: 1px solid rgba(52, 211, 153, .4);
        padding: 8px 16px;
        border-radius: 24px;
        color: #6EE7B7;
        font-size: .76rem;
        font-weight: 700;
        white-space: nowrap;
        flex-shrink: 0;
        display: flex;
        align-items: center;
        gap: 6px;
      }

      /* ── Cinta de Metadatos del Canal ── */
      .sim-meta-ribbon {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 12px 20px;
        margin-bottom: 1.25rem;
        display: flex;
        flex-wrap: wrap;
        gap: 24px;
        align-items: center;
        box-shadow: 0 1px 3px rgba(15, 23, 42, .04);
      }
      .sim-meta-item {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        font-size: .78rem;
        color: #64748B;
      }
      .sim-meta-item strong {
        color: #0F172A;
        font-weight: 700;
      }
      .sim-meta-pill {
        background: #ECFDF5;
        border: 1px solid #A7F3D0;
        color: #047857;
        font-size: .7rem;
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 6px;
      }

      /* ── Tarjetas Contenedoras ── */
      .sim-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 1px 4px rgba(15, 23, 42, .05);
        margin-bottom: 1rem;
      }
      .sim-card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-bottom: 12px;
        border-bottom: 1px solid #F1F5F9;
        margin-bottom: 14px;
      }
      .sim-card-title {
        font-size: .88rem;
        font-weight: 750;
        color: #0F172A;
        display: flex;
        align-items: center;
        gap: 8px;
        letter-spacing: -.01em;
      }
      .sim-card-subtitle {
        font-size: .72rem;
        color: #64748B;
        font-weight: 500;
      }

      /* ── Chat WhatsApp Header ── */
      .wa-chat-header {
        background: #075E54;
        background: linear-gradient(90deg, #075E54 0%, #128C7E 100%);
        border-radius: 10px 10px 0 0;
        padding: 12px 18px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        color: #FFFFFF;
        margin: -20px -20px 16px -20px;
      }
      .wa-chat-profile {
        display: flex;
        align-items: center;
        gap: 12px;
      }
      .wa-avatar {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: #25D366;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.15);
      }
      .wa-name {
        font-size: .88rem;
        font-weight: 700;
        color: #FFFFFF;
        line-height: 1.2;
      }
      .wa-status {
        font-size: .7rem;
        color: #D1FAE5;
        display: flex;
        align-items: center;
        gap: 4px;
      }
      .wa-status-dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: #34D399;
        display: inline-block;
      }

      /* ── Chat Empty State & Hints ── */
      .wa-empty-box {
        background: #F8FAFC;
        border: 1px dashed #CBD5E1;
        border-radius: 10px;
        padding: 24px 18px;
        text-align: center;
        margin: 10px 0 16px;
      }
      .wa-empty-title {
        font-size: .88rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 4px;
      }
      .wa-empty-desc {
        font-size: .76rem;
        color: #64748B;
        line-height: 1.45;
        max-width: 440px;
        margin: 0 auto 12px;
      }
      .wa-hint-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 8px;
        margin-top: 10px;
        text-align: left;
      }
      .wa-hint-chip {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 8px 10px;
        font-size: .72rem;
        color: #334155;
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
      }
      .wa-hint-chip strong {
        color: #047857;
        display: block;
        font-size: .68rem;
        text-transform: uppercase;
        letter-spacing: .03em;
        margin-bottom: 2px;
      }

      /* ── Extraction Details ── */
      .ia-entity-card {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 12px 14px;
        margin-bottom: 10px;
        transition: all .2s ease;
      }
      .ia-entity-card.detected {
        background: #F0FDF4;
        border-color: #BBF7D0;
        border-left: 4px solid #10B981;
      }
      .ia-entity-label {
        font-size: .68rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: .06em;
        color: #64748B;
        margin-bottom: 4px;
      }
      .ia-entity-value {
        font-size: .92rem;
        font-weight: 700;
        color: #0F172A;
        display: flex;
        align-items: center;
        justify-content: space-between;
      }
      .ia-entity-value.empty {
        color: #94A3B8;
        font-weight: 500;
      }
      .ia-badge-pill {
        font-size: .7rem;
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 999px;
      }
      .ia-badge-pill.yes { background: #DCFCE7; color: #15803D; border: 1px solid #86EFAC; }
      .ia-badge-pill.no { background: #FEE2E2; color: #B91C1C; border: 1px solid #FCA5A5; }
      .ia-badge-pill.none { background: #F1F5F9; color: #94A3B8; border: 1px solid #E2E8F0; }
      .ia-badge-pill.highlight { background: #E0E7FF; color: #3730A3; border: 1px solid #C7D2FE; }

      /* ── Success Alert Card ── */
      .saved-lead-card {
        background: linear-gradient(135deg, #ECFDF5 0%, #D1FAE5 100%);
        border: 1px solid #6EE7B7;
        border-left: 5px solid #10B981;
        border-radius: 10px;
        padding: 16px 20px;
        margin-top: 1rem;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.12);
      }
      .saved-lead-title {
        font-size: .92rem;
        font-weight: 800;
        color: #065F46;
        margin-bottom: .35rem;
        display: flex;
        align-items: center;
        gap: 6px;
      }
      .saved-lead-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        font-size: .78rem;
        color: #047857;
        align-items: center;
        margin-bottom: .65rem;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Catálogo de motocicletas (caché de 60s) ──────────────────────────────────
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

if "estado_conversacional" not in st.session_state:
    st.session_state["estado_conversacional"] = None

# ── Hero Banner ──────────────────────────────────────────────────────────────
st.markdown(
    """
    <section class="sim-hero">
      <div>
        <div class="sim-hero-eyebrow">
          <span>●</span> Canal Digital · WhatsApp Business
        </div>
        <div class="sim-hero-title">Simulador de Conversación WhatsApp</div>
        <div class="sim-hero-sub">
          Prueba en tiempo real el pipeline de ingesta conversacional: extracción automática de modelo,
          cuota inicial e intención de compra, cálculo del scoring comercial y persistencia directa en PostgreSQL.
        </div>
      </div>
      <div class="sim-hero-badge">
        <span>💬</span> WhatsApp Bot v1.0
      </div>
    </section>
    """,
    unsafe_allow_html=True,
)

# ── Cinta de Metadatos del Canal ─────────────────────────────────────────────
st.markdown(
    """
    <div class="sim-meta-ribbon">
      <div class="sim-meta-item">
        <span>📱</span> Canal: <span class="sim-meta-pill">WhatsApp</span>
      </div>
      <div class="sim-meta-item">
        <span>🏢</span> Empresa: <strong>Motos Andinas (EMP-01)</strong>
      </div>
      <div class="sim-meta-item">
        <span>📍</span> Punto de venta: <strong>Motos Andinas Armenia (PV-002)</strong>
      </div>
      <div class="sim-meta-item">
        <span>🤖</span> Asistente: <strong>Bot Comercial de Ingesta</strong>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ── Respuestas automáticas del bot (reglas simples — preservadas intactas) ───
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


# ── Extracción acumulada unificada (NLP + EstadoConversacional) ───────────────
mensajes = st.session_state["sim_mensajes"]
estado_dict = st.session_state.get("estado_conversacional")
estado_actual = EstadoConversacional.from_dict(estado_dict) if estado_dict else EstadoConversacional()

raw_nlp = extract_conversation(mensajes, catalogo) if mensajes else {}
extraccion = build_extraction_view(estado_actual, raw_nlp) if mensajes else {}

sku_detectado = extraccion.get("sku_motocicleta")
pago_detectado = extraccion.get("pago_inicial")
metodo_pago = extraccion.get("metodo_pago")
intencion = extraccion.get("intencion_declarada")
solicita_cot = extraccion.get("solicita_cotizacion")
solicita_cit = extraccion.get("solicita_cita")
ciudad_sede_val = extraccion.get("ciudad_sede")

moto_info = catalogo_by_sku.get(sku_detectado) if sku_detectado else None
nombre_moto = f"{moto_info['marca']} {moto_info['linea']}" if moto_info else None

# ── Layout principal en 2 Columnas ───────────────────────────────────────────
col_chat, col_ia = st.columns([7, 5], gap="large")

# ═════════════════════════════════════════════════════════════════════════════
# PANEL IZQUIERDO: Conversación WhatsApp
# ═════════════════════════════════════════════════════════════════════════════
with col_chat:
    with st.container():
        st.markdown(
            """
            <div class="wa-chat-header">
              <div class="wa-chat-profile">
                <div class="wa-avatar">💬</div>
                <div>
                  <div class="wa-name">Asesor Virtual · Motos Andinas</div>
                  <div class="wa-status"><span class="wa-status-dot"></span> WhatsApp Business · En línea</div>
                </div>
              </div>
              <div style="font-size: .75rem; color: #D1FAE5; opacity: .9;">
                Canal Simulado
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if not mensajes:
            st.markdown(
                """
                <div class="wa-empty-box">
                  <div class="wa-empty-title">💬 Inicia una conversación por WhatsApp</div>
                  <div class="wa-empty-desc">
                    Escribe un mensaje como prospecto para ver cómo el sistema extrae las entidades clave
                    (modelo, cuota inicial, forma de pago) y calcula el score en tiempo real.
                  </div>
                  <div class="wa-hint-grid">
                    <div class="wa-hint-chip">
                      <strong>Ejemplo 1 · Modelo</strong>
                      "Hola, quiero información sobre la Pulsar NS 200"
                    </div>
                    <div class="wa-hint-chip">
                      <strong>Ejemplo 2 · Financiación</strong>
                      "Tengo 2 millones de cuota inicial para financiar"
                    </div>
                    <div class="wa-hint-chip">
                      <strong>Ejemplo 3 · Cotización</strong>
                      "¿Me pueden enviar una cotización formal?"
                    </div>
                    <div class="wa-hint-chip">
                      <strong>Ejemplo 4 · Cita en Agencia</strong>
                      "Quiero agendar una cita para ir a la agencia"
                    </div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Renderizar historial de mensajes
        for msg in mensajes:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                st.caption(msg.get("hora", ""))

        # Input de chat
        texto_usuario = st.chat_input("Escribe un mensaje en WhatsApp...")

        if texto_usuario and texto_usuario.strip():
            hora_ahora = datetime.now().strftime("%H:%M")

            st.session_state["sim_mensajes"].append({
                "role": "user",
                "content": texto_usuario.strip(),
                "hora": hora_ahora,
            })

            estado_dict = st.session_state.get("estado_conversacional")
            estado_previo = EstadoConversacional.from_dict(estado_dict) if estado_dict else None

            respuesta, nuevo_estado = process_turn(
                st.session_state["sim_mensajes"],
                catalogo,
                estado_previo=estado_previo
            )
            st.session_state["estado_conversacional"] = nuevo_estado.to_dict()

            st.session_state["sim_mensajes"].append({
                "role": "assistant",
                "content": respuesta,
                "hora": hora_ahora,
            })

            st.rerun()

        # Barra de Acciones del Chat
        if mensajes:
            st.markdown("<div style='margin-top:0.9rem;'></div>", unsafe_allow_html=True)
            col_acc1, col_acc2 = st.columns([3, 2])

            with col_acc1:
                btn_guardar = st.button(
                    "💾  Guardar conversación en PostgreSQL",
                    type="primary",
                    use_container_width=True,
                )
                if btn_guardar:
                    tiene_msg_user = any(m.get("role") in ("user", "cliente") for m in mensajes)
                    if not tiene_msg_user:
                        st.warning("Se requiere al menos un mensaje del cliente para guardar.")
                    else:
                        try:
                            res_persistencia = guardar_conversacion_simulada(
                                messages=mensajes,
                                catalogo=catalogo,
                                nombre_cliente="Cliente WhatsApp Simulado",
                                empresa_id="EMP-01",
                                punto_venta_id="PV-002",
                                extraccion_override=extraccion,
                            )
                            st.session_state["ultimo_guardado"] = res_persistencia
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar conversación en PostgreSQL: {e}")

            with col_acc2:
                if st.button("↺  Limpiar chat", type="secondary", use_container_width=True):
                    st.session_state["sim_mensajes"] = []
                    st.session_state["ultimo_guardado"] = None
                    st.session_state["estado_conversacional"] = None
                    st.rerun()

        # Notificación elegante de guardado exitoso
        if st.session_state.get("ultimo_guardado"):
            info_g = st.session_state["ultimo_guardado"]
            sc = info_g.get("scoring", {})
            lead_id_guardado = info_g.get("lead_id", "—")
            conv_id_guardado = info_g.get("conversacion_id", "—")
            score_num = sc.get("puntaje_prioridad")
            score_str = f"{float(score_num):.2f}" if score_num is not None else "—"
            temp_val = sc.get("temperatura")
            badge_temp_html = badge_temperatura(temp_val)

            st.markdown(
                f"""
                <div class="saved-lead-card">
                  <div class="saved-lead-title">
                    <span>✅</span> Conversación persistida con éxito en PostgreSQL
                  </div>
                  <div class="saved-lead-meta">
                    <span>Lead ID: <strong style="color:#064E3B;">#{html.escape(lead_id_guardado)}</strong></span>
                    <span>·</span>
                    <span>Conversación: <strong>{html.escape(conv_id_guardado)}</strong></span>
                    <span>·</span>
                    <span>Score: <strong>{score_str}</strong></span>
                    <span>·</span>
                    {badge_temp_html}
                  </div>
                  <div style="font-size: .75rem; color: #047857;">
                    El lead ya se encuentra disponible en la <b>Bandeja de Leads</b> y en el <b>Dashboard operativo</b>.
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            # Guardar en session state para permitir navegación directa
            st.session_state["lead_id_seleccionado"] = lead_id_guardado
            st.page_link(
                "pages/3_Detalle_Lead.py",
                label=f"Ver ficha completa de #{lead_id_guardado}  ➔",
            )


# ═════════════════════════════════════════════════════════════════════════════
# PANEL DERECHO: Extracción IA en Tiempo Real
# ═════════════════════════════════════════════════════════════════════════════
with col_ia:
    st.markdown(
        """
        <div class="sim-card">
          <div class="sim-card-header">
            <div>
              <div class="sim-card-title">
                <span>🤖</span> Extracción IA en Tiempo Real
              </div>
              <div class="sim-card-subtitle">Entidades detectadas automáticamente desde WhatsApp</div>
            </div>
            <span style="background:#EEF2FF; border:1px solid #C7D2FE; color:#4338CA;
                         font-size:.7rem; font-weight:700; padding:3px 9px; border-radius:6px;">
              NLP ENGINE
            </span>
          </div>
        """,
        unsafe_allow_html=True,
    )

    # 1. Motocicleta / Modelo
    card_moto_cls = "ia-entity-card detected" if sku_detectado else "ia-entity-card"
    if nombre_moto and sku_detectado:
        moto_val_html = f"""
        <span>{html.escape(nombre_moto)}</span>
        <span class="ia-badge-pill highlight">{html.escape(sku_detectado)}</span>
        """
    else:
        moto_val_html = '<span class="ia-entity-value empty">—</span>'

    st.markdown(
        f"""
        <div class="{card_moto_cls}">
          <div class="ia-entity-label">🏍️ Motocicleta / Modelo de interés</div>
          <div class="ia-entity-value">{moto_val_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 2. Cuota inicial / Pago inicial
    card_pago_cls = "ia-entity-card detected" if pago_detectado is not None else "ia-entity-card"
    if pago_detectado == "NO_APLICA":
        pago_val_html = """
        <span style="color:#64748B;">No aplica (Contado)</span>
        <span class="ia-badge-pill" style="background:#F1F5F9; color:#475569;">No aplica</span>
        """
    elif pago_detectado is not None:
        if isinstance(pago_detectado, (int, float)) and pago_detectado > 0:
            pago_str = f"${int(pago_detectado):,}".replace(",", ".")
            pago_val_html = f"""
            <span style="color:#047857;">{pago_str}</span>
            <span class="ia-badge-pill yes">Cuota declarada</span>
            """
        else:
            pago_val_html = """
            <span style="color:#B45309;">$0 (Sin inicial)</span>
            <span class="ia-badge-pill" style="background:#FEF3C7; color:#92400E;">0 cuota</span>
            """
    else:
        pago_val_html = '<span class="ia-entity-value empty">—</span>'

    st.markdown(
        f"""
        <div class="{card_pago_cls}">
          <div class="ia-entity-label">💵 Pago / Cuota Inicial</div>
          <div class="ia-entity-value">{pago_val_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 3. Método de pago & Intención declarada (Fila doble)
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        card_met_cls = "ia-entity-card detected" if metodo_pago else "ia-entity-card"
        if metodo_pago:
            met_val_html = f'<span style="color:#0F172A;">{html.escape(metodo_pago)}</span>'
        else:
            met_val_html = '<span class="ia-entity-value empty">—</span>'

        st.markdown(
            f"""
            <div class="{card_met_cls}">
              <div class="ia-entity-label">💳 Método de Pago</div>
              <div class="ia-entity-value">{met_val_html}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_e2:
        card_int_cls = "ia-entity-card detected" if intencion else "ia-entity-card"
        if intencion:
            int_val_html = f'<span style="color:#0F172A;">{html.escape(intencion)}</span>'
        else:
            int_val_html = '<span class="ia-entity-value empty">—</span>'

        st.markdown(
            f"""
            <div class="{card_int_cls}">
              <div class="ia-entity-label">🎯 Intención</div>
              <div class="ia-entity-value">{int_val_html}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 4. Solicitud de Cotización & Cita Comercial
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        card_cot_cls = "ia-entity-card detected" if solicita_cot is not None else "ia-entity-card"
        if solicita_cot is True:
            cot_html = '<span class="ia-badge-pill yes">✓ Sí solicita</span>'
        elif solicita_cot is False:
            cot_html = '<span class="ia-badge-pill no">✗ Rechaza</span>'
        else:
            cot_html = '<span class="ia-badge-pill none">—</span>'

        st.markdown(
            f"""
            <div class="{card_cot_cls}">
              <div class="ia-entity-label">📄 Cotización Formal</div>
              <div class="ia-entity-value">{cot_html}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_s2:
        card_cit_cls = "ia-entity-card detected" if solicita_cit is not None else "ia-entity-card"
        if solicita_cit is True:
            cit_html = '<span class="ia-badge-pill yes">✓ Sí solicita</span>'
        elif solicita_cit is False:
            cit_html = '<span class="ia-badge-pill no">✗ Rechaza</span>'
        else:
            cit_html = '<span class="ia-badge-pill none">—</span>'

        st.markdown(
            f"""
            <div class="{card_cit_cls}">
              <div class="ia-entity-label">📅 Cita en Agencia</div>
              <div class="ia-entity-value">{cit_html}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 5. Sede / Ciudad
    if ciudad_sede_val:
        st.markdown(
            f"""
            <div class="ia-entity-card detected">
              <div class="ia-entity-label">📍 Sede / Ciudad</div>
              <div class="ia-entity-value"><span style="color:#0F172A; font-weight:700;">{html.escape(ciudad_sede_val)}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Pie explicativo de extracción
    st.markdown(
        """
        <div style="margin-top:12px; padding-top:10px; border-top:1px solid #F1F5F9;
                    display:flex; justify-content:space-between; align-items:center; font-size:.72rem; color:#94A3B8;">
          <span>Pipeline: <code>extract_conversation</code></span>
          <span>Preservación NULL: <code>Estricta</code></span>
        </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
