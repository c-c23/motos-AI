import os
import re
import requests
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from database import get_connection
from queries.leads_queries import get_catalogo_motocicletas
from services.extraction_service import (
    extract_motocicleta,
    extract_metodo_pago,
    extract_pago_inicial,
    extract_solicita_cita,
    extract_solicita_cotizacion,
)

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL = "https://motos-ai.onrender.com/api/v1/leads/telegram"

AFIRMATIVOS = ["si", "sí", "claro", "dale", "correcto", "por supuesto", "de acuerdo", "me gustaria", "quisiera", "quiero"]
NEGATIVOS = ["no", "nop", "no gracias", "por ahora no", "mas adelante", "despues"]


def _limpiar_estado(state: dict) -> None:
    for key in (
        "estado",
        "nombre",
        "telefono",
        "motocicleta",
        "metodo_pago",
        "pago_inicial",
        "solicita_cotizacion",
        "solicita_cita",
        "mensajes",
    ):
        state.pop(key, None)


def normalizar_telefono(texto: str) -> str | None:
    if not texto:
        return None

    candidatos = re.findall(r'(?:\+?57\s*[-.]?)?3\d{9}', texto.strip())
    if not candidatos:
        candidatos = [re.sub(r'\D', '', texto.strip())]

    for candidato in candidatos:
        numero = re.sub(r'\D', '', candidato)
        if len(numero) == 11 and numero.startswith("57"):
            numero = numero[2:]
        if len(numero) == 10 and numero.startswith("3"):
            return numero

    return None


def extraer_nombre(texto: str) -> str | None:
    texto_limpio = texto.strip()
    if not texto_limpio:
        return None

    patrones = [
        r'(?:soy|me llamo|mi nombre es|mi nombre\s+es)\s+([a-zA-ZáéíóúÁÉÍÓÚñÑüÜ]+(?:\s+[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ]+)*)',
        r'([A-Z][a-zA-ZáéíóúÁÉÍÓÚñÑüÜ]+(?:\s+[A-Z][a-zA-ZáéíóúÁÉÍÓÚñÑüÜ]+)*)',
    ]

    for patron in patrones:
        match = re.search(patron, texto_limpio, flags=re.IGNORECASE)
        if match:
            nombre = match.group(1).strip()
            if len(nombre.split()) <= 3:
                return nombre

    if len(texto_limpio.split()) <= 3 and all(palabra.isalpha() for palabra in texto_limpio.split()):
        return texto_limpio

    return None


def _extraer_modelo_desde_mensajes(mensajes: list[dict], catalogo: list[dict]) -> str | None:
    if not catalogo or not mensajes:
        return None
    sku = extract_motocicleta(mensajes, catalogo)
    if not sku:
        return None
    for moto in catalogo:
        if moto.get("sku") == sku:
            return moto.get("linea") or moto.get("modelo") or sku
    return sku


def _respuesta_si_no(texto: str) -> bool | None:
    entrada = texto.strip().lower()
    if not entrada:
        return None
    if any(palabra in entrada for palabra in AFIRMATIVOS):
        return True
    if any(palabra in entrada for palabra in NEGATIVOS):
        return False
    return None


def _cargar_catalogo() -> list[dict]:
    try:
        with get_connection() as conn:
            return get_catalogo_motocicletas(conn)
    except Exception:
        return []


def iniciar_flujo_telegram(state: dict | None = None) -> dict:
    nueva = dict(state) if state else {}
    _limpiar_estado(nueva)
    nueva["estado"] = "esperando_nombre"
    nueva["mensajes"] = []
    nueva["nombre"] = None
    nueva["telefono"] = None
    nueva["motocicleta"] = None
    nueva["metodo_pago"] = None
    nueva["pago_inicial"] = None
    nueva["solicita_cotizacion"] = None
    nueva["solicita_cita"] = None
    return nueva


def _actualizar_datos_desde_conversacion(state: dict, catalogo: list[dict]) -> dict:
    mensajes = state.get("mensajes", [])
    if not mensajes:
        return state

    if state.get("nombre") is None:
        for msg in reversed(mensajes):
            if msg.get("role") == "user":
                nombre = extraer_nombre(msg.get("content") or "")
                if nombre:
                    state["nombre"] = nombre
                    break

    if state.get("telefono") is None:
        for msg in reversed(mensajes):
            if msg.get("role") == "user":
                telefono = normalizar_telefono(msg.get("content") or "")
                if telefono:
                    state["telefono"] = telefono
                    break

    if state.get("motocicleta") is None:
        moto = _extraer_modelo_desde_mensajes(mensajes, catalogo)
        if moto:
            state["motocicleta"] = moto

    if state.get("metodo_pago") is None:
        metodo = extract_metodo_pago(mensajes)
        if metodo in ("Contado", "Crédito"):
            state["metodo_pago"] = metodo

    if state.get("pago_inicial") is None and state.get("metodo_pago") == "Crédito":
        inicial = extract_pago_inicial(mensajes)
        if inicial is not None:
            state["pago_inicial"] = inicial

    if state.get("solicita_cotizacion") is None:
        cot = extract_solicita_cotizacion(mensajes)
        if cot is not None:
            state["solicita_cotizacion"] = cot

    if state.get("solicita_cita") is None:
        cita = extract_solicita_cita(mensajes)
        if cita is not None:
            state["solicita_cita"] = cita

    return state


def _resolver_estado_siguiente(state: dict) -> str:
    if not state.get("nombre"):
        return "esperando_nombre"
    if not state.get("telefono"):
        return "esperando_telefono"
    if not state.get("motocicleta"):
        return "esperando_motocicleta"
    if not state.get("metodo_pago"):
        return "esperando_metodo_pago"
    if state.get("metodo_pago") == "Crédito" and state.get("pago_inicial") is None:
        return "esperando_pago_inicial"
    if state.get("solicita_cotizacion") is None:
        return "esperando_solicita_cotizacion"
    if state.get("solicita_cita") is None:
        return "esperando_solicita_cita"
    return "finalizado"


def procesar_mensaje_telegram(state: dict, texto: str, catalogo: list[dict] | None = None) -> dict:
    if not texto or not texto.strip():
        return state

    comando = texto.strip().lower()
    if comando in ("/cancelar", "cancelar"):
        state["estado"] = "cancelado"
        state["nombre"] = None
        state["telefono"] = None
        state["motocicleta"] = None
        state["metodo_pago"] = None
        state["pago_inicial"] = None
        state["solicita_cotizacion"] = None
        state["solicita_cita"] = None
        state["mensajes"] = []
        return state

    state.setdefault("mensajes", []).append({"role": "user", "content": texto.strip()})
    catalogo = catalogo or _cargar_catalogo()
    state = _actualizar_datos_desde_conversacion(state, catalogo)

    estado = state.get("estado")
    if estado in (None, "inicio", "cancelado"):
        state["estado"] = "esperando_nombre"
        return state

    proximo_estado = _resolver_estado_siguiente(state)
    if estado in (
        "esperando_nombre",
        "esperando_telefono",
        "esperando_motocicleta",
        "esperando_metodo_pago",
        "esperando_pago_inicial",
        "esperando_solicita_cotizacion",
        "esperando_solicita_cita",
    ) and proximo_estado != estado:
        state["estado"] = proximo_estado
        return state

    if estado == "esperando_nombre":
        nombre = extraer_nombre(texto)
        if nombre:
            state["nombre"] = nombre
            state["estado"] = "esperando_telefono"
        return state

    if estado == "esperando_telefono":
        telefono = normalizar_telefono(texto)
        if telefono:
            state["telefono"] = telefono
            state["estado"] = "esperando_motocicleta"
        else:
            state["telefono"] = None
        return state

    if estado == "esperando_motocicleta":
        if state.get("motocicleta"):
            state["estado"] = "esperando_metodo_pago"
        return state

    if estado == "esperando_metodo_pago":
        metodo = extract_metodo_pago(state["mensajes"])
        if metodo in ("Contado", "Crédito"):
            state["metodo_pago"] = metodo
            if metodo == "Crédito":
                state["estado"] = "esperando_pago_inicial"
            else:
                state["pago_inicial"] = None
                state["estado"] = "esperando_solicita_cotizacion"
        return state

    if estado == "esperando_pago_inicial":
        if state.get("metodo_pago") == "Crédito":
            inicial = extract_pago_inicial(state["mensajes"])
            if inicial is not None:
                state["pago_inicial"] = inicial
                state["estado"] = "esperando_solicita_cotizacion"
        return state

    if estado == "esperando_solicita_cotizacion":
        decision = _respuesta_si_no(texto)
        if decision is not None:
            state["solicita_cotizacion"] = decision
            state["estado"] = "esperando_solicita_cita"
        return state

    if estado == "esperando_solicita_cita":
        decision = _respuesta_si_no(texto)
        if decision is not None:
            state["solicita_cita"] = decision
            state["estado"] = _resolver_estado_siguiente(state)
        return state

    if estado == "finalizado":
        return state

    state["estado"] = _resolver_estado_siguiente(state)
    return state


def build_telegram_payload(
    nombre: str,
    telefono: str | None,
    mensaje: str,
    motocicleta: str | None,
    metodo_pago: str | None,
    pago_inicial: int | None,
    solicita_cotizacion: bool | None,
    solicita_cita: bool | None,
    empresa_id: str = "EMP-01",
    punto_venta_id: str = "PV-001",
    telegram_user_id: str = "",
) -> dict:
    return {
        "telegram_user_id": str(telegram_user_id),
        "nombre": nombre,
        "telefono": telefono,
        "mensaje": mensaje,
        "motocicleta": motocicleta,
        "metodo_pago": metodo_pago,
        "pago_inicial": pago_inicial,
        "solicita_cotizacion": solicita_cotizacion,
        "solicita_cita": solicita_cita,
        "empresa_id": empresa_id,
        "punto_venta_id": punto_venta_id,
    }


def _siguiente_mensaje_bot(state: dict) -> str:
    estado = state.get("estado")
    nombre = (state.get("nombre") or "cliente").strip()

    if estado == "esperando_nombre":
        return "¡Hola! Bienvenido a Motos AI. 🏍️\n\nPara ayudarte, primero necesito algunos datos. ¿Cuál es tu nombre?"
    if estado == "esperando_telefono":
        return f"Mucho gusto, {nombre} 👋\n\n¿Cuál es tu número de teléfono?"
    if estado == "esperando_motocicleta":
        return "Perfecto 👍\n\nAhora cuéntame, ¿qué motocicleta estás buscando?"
    if estado == "esperando_metodo_pago":
        return "¡Excelente elección! 🏍️\n\n¿Deseas realizar la compra de contado o mediante financiación?"
    if estado == "esperando_pago_inicial":
        return "Perfecto. ¿Con cuánto dinero cuentas aproximadamente para la cuota inicial?"
    if estado == "esperando_solicita_cotizacion":
        return "¿Deseas que te generemos una cotización formal?"
    if estado == "esperando_solicita_cita":
        return "¿Te gustaría agendar una cita en el concesionario?"
    if estado == "cancelado":
        return "Conversación cancelada. 👍\n\nCuando quieras comenzar nuevamente, escribe /start"
    if estado == "finalizado":
        return "¡Perfecto! Hemos registrado tu solicitud. Un asesor podrá ayudarte con la cotización y cita."
    return "Para comenzar una nueva solicitud, escribe /start"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data.update(iniciar_flujo_telegram(context.user_data))
    await update.message.reply_text(_siguiente_mensaje_bot(context.user_data))


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["estado"] = "cancelado"
    await update.message.reply_text(_siguiente_mensaje_bot(context.user_data))


async def recibir_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    texto = update.message.text.strip()
    if not texto:
        await update.message.reply_text("Por favor escribe una respuesta.")
        return

    state = context.user_data or {}
    if not isinstance(state, dict):
        state = {}

    estado_anterior = state.get("estado")
    catalogo = _cargar_catalogo()
    state = procesar_mensaje_telegram(state, texto, catalogo=catalogo)

    context.user_data.clear()
    context.user_data.update(state)

    if state.get("estado") == "esperando_telefono" and state.get("telefono") is None and estado_anterior == "esperando_telefono":
        await update.message.reply_text(
            "El número parece no tener un formato válido. 📱\n\n"
            "Por favor escribe un número de teléfono de 10 dígitos.\n"
            "Ejemplo: 3001234567"
        )
        return

    if state.get("estado") == "esperando_metodo_pago":
        respuesta = _siguiente_mensaje_bot(state)
        await update.message.reply_text(respuesta)
        return

    if state.get("estado") == "esperando_pago_inicial" and state.get("metodo_pago") == "Crédito":
        await update.message.reply_text(_siguiente_mensaje_bot(state))
        return

    if state.get("estado") in ("esperando_solicita_cotizacion", "esperando_solicita_cita"):
        await update.message.reply_text(_siguiente_mensaje_bot(state))
        return

    if state.get("estado") == "finalizado":
        nombre = state.get("nombre") or "cliente"
        telefono = state.get("telefono")
        mensaje_final = " ".join(
            m.get("content", "")
            for m in state.get("mensajes", [])
            if m.get("role") == "user"
        )
        if not mensaje_final:
            mensaje_final = texto

        payload = build_telegram_payload(
            nombre=nombre,
            telefono=telefono,
            mensaje=mensaje_final,
            motocicleta=state.get("motocicleta"),
            metodo_pago=state.get("metodo_pago"),
            pago_inicial=state.get("pago_inicial"),
            solicita_cotizacion=state.get("solicita_cotizacion"),
            solicita_cita=state.get("solicita_cita"),
            empresa_id="EMP-01",
            punto_venta_id="PV-001",
            telegram_user_id=str(update.effective_user.id),
        )

        try:
            response = requests.post(API_URL, json=payload, timeout=30)
            if response.status_code == 200:
                resultado = response.json()
                lead_id = resultado.get("lead_id")
                conversacion_id = resultado.get("conversacion_id")
                await update.message.reply_text(
                    "¡Perfecto! Hemos registrado tu solicitud. Un asesor podrá ayudarte con la cotización y cita."
                )
                print(f"Lead creado: {lead_id} | Conversación: {conversacion_id}")
            else:
                print(f"Error API: {response.status_code} {response.text}")
                await update.message.reply_text(
                    "Tuvimos un problema procesando tu solicitud. Por favor intenta nuevamente."
                )
        except requests.RequestException as exc:
            print("Error de conexión con la API:", exc)
            await update.message.reply_text(
                "No fue posible conectar con el sistema. Por favor intenta nuevamente."
            )
        return

    await update.message.reply_text(_siguiente_mensaje_bot(state))


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("Falta TELEGRAM_BOT_TOKEN en el archivo .env")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancelar", cancelar))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_mensaje))

    print("Bot de Telegram iniciado...")
    application.run_polling()


if __name__ == "__main__":
    main()
