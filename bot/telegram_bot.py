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
    await update.message.reply_text(
        "Hola 👋 Soy el asistente de Motos AI.\n\n"
        "Cuéntame qué motocicleta estás buscando."
    )


async def recibir_mensaje(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message or not update.message.text:
        return

    usuario = update.effective_user

    payload = {
        "telegram_user_id": str(usuario.id),
        "nombre": usuario.full_name,
        "telefono": None,
        "mensaje": update.message.text,
    }

    try:
        response = requests.post(
            API_URL,
            json=payload,
            timeout=30,
        )

        if response.status_code == 200:
            resultado = response.json()

            await update.message.reply_text(
                "¡Gracias! Hemos recibido tu solicitud. 🏍️\n"
                "Un asesor podrá ayudarte pronto."
            )

            print(
                "Lead creado:",
                resultado.get("lead_id"),
                resultado.get("conversacion_id"),
            )

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
        print("Error de conexión con la API:", exc)

        await update.message.reply_text(
            "No fue posible conectar con el sistema. "
            "Por favor intenta nuevamente."
        )


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError(
            "Falta TELEGRAM_BOT_TOKEN en el archivo .env"
        )

    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

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