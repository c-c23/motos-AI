import os
import requests

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

API_URL = "https://motos-ai.onrender.com/api/v1/leads/telegram"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Inicia una nueva conversación con el usuario.
    """

    # Limpiar cualquier conversación anterior
    context.user_data.clear()

    await update.message.reply_text(
        "Hola 👋 Soy el asistente de Motos AI.\n\n"
        "Para ayudarte mejor, primero necesito algunos datos.\n\n"
        "¿Cuál es tu nombre?"
    )

    context.user_data["estado"] = "esperando_nombre"


async def recibir_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Gestiona los mensajes según el estado actual de la conversación.
    """

    if not update.message or not update.message.text:
        return

    texto = update.message.text.strip()

    if not texto:
        await update.message.reply_text(
            "Por favor, escribe una respuesta."
        )
        return

    estado = context.user_data.get("estado")

    # ---------------------------------------------------------
    # 1. ESPERANDO NOMBRE
    # ---------------------------------------------------------
    if estado == "esperando_nombre":

        context.user_data["nombre"] = texto
        context.user_data["estado"] = "esperando_telefono"

        await update.message.reply_text(
            f"Mucho gusto, {texto} 👋\n\n"
            "¿Cuál es tu número de teléfono?"
        )

        return

    # ---------------------------------------------------------
    # 2. ESPERANDO TELÉFONO
    # ---------------------------------------------------------
    if estado == "esperando_telefono":

        telefono = texto

        # Normalización básica del teléfono:
        # elimina espacios, guiones y paréntesis.
        telefono_normalizado = (
            telefono
            .replace(" ", "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
        )

        # Validación básica para Colombia.
        # Permitimos números de 10 dígitos.
        if (
            not telefono_normalizado.isdigit()
            or len(telefono_normalizado) != 10
        ):
            await update.message.reply_text(
                "El número parece no tener un formato válido. 📱\n\n"
                "Por favor escribe un número de teléfono de 10 dígitos.\n"
                "Ejemplo: 3001234567"
            )
            return

        context.user_data["telefono"] = telefono_normalizado
        context.user_data["estado"] = "esperando_interes"

        await update.message.reply_text(
            "Perfecto 👍\n\n"
            "Ahora cuéntame, ¿qué motocicleta estás buscando?"
        )

        return

    # ---------------------------------------------------------
    # 3. ESPERANDO INTERÉS / MENSAJE DEL CLIENTE
    # ---------------------------------------------------------
    if estado == "esperando_interes":

        nombre = context.user_data.get("nombre")
        telefono = context.user_data.get("telefono")

        usuario = update.effective_user

        payload = {
            "telegram_user_id": str(usuario.id),
            "nombre": nombre,
            "telefono": telefono,
            "mensaje": texto,
        }

        try:
            response = requests.post(
                API_URL,
                json=payload,
                timeout=30,
            )

            if response.status_code == 200:

                resultado = response.json()

                lead_id = resultado.get("lead_id")
                conversacion_id = resultado.get("conversacion_id")

                await update.message.reply_text(
                    "¡Gracias! Hemos recibido tu solicitud. 🏍️\n\n"
                    "Un asesor podrá ayudarte pronto."
                )

                print(
                    "Lead creado:",
                    lead_id,
                    "| Conversación:",
                    conversacion_id,
                )

                # Limpiar la conversación después de procesarla.
                context.user_data.clear()

            else:

                print(
                    "Error API:",
                    response.status_code,
                    response.text,
                )

                await update.message.reply_text(
                    "Tuvimos un problema procesando tu solicitud. "
                    "Por favor intenta nuevamente."
                )

        except requests.RequestException as exc:

            print(
                "Error de conexión con la API:",
                exc,
            )

            await update.message.reply_text(
                "No fue posible conectar con el sistema. "
                "Por favor intenta nuevamente."
            )

        return

    # ---------------------------------------------------------
    # 4. ESTADO DESCONOCIDO / CONVERSACIÓN NO INICIADA
    # ---------------------------------------------------------
    await update.message.reply_text(
        "Para comenzar una nueva solicitud, escribe /start"
    )


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Cancela la conversación actual.
    """

    context.user_data.clear()

    await update.message.reply_text(
        "Conversación cancelada. 👍\n\n"
        "Cuando quieras comenzar nuevamente, escribe /start"
    )


def main():
    """
    Punto de entrada del bot.
    """

    if not TELEGRAM_BOT_TOKEN:
        raise ValueError(
            "Falta TELEGRAM_BOT_TOKEN en el archivo .env"
        )

    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    # Comando para iniciar conversación
    application.add_handler(
        CommandHandler("start", start)
    )

    # Comando para cancelar conversación
    application.add_handler(
        CommandHandler("cancelar", cancelar)
    )

    # Mensajes de texto normales
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            recibir_mensaje,
        )
    )

    print("Bot de Telegram iniciado...")

    application.run_polling()


if __name__ == "__main__":
    main()

