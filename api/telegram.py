from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from database import get_connection
from queries.persistence_queries import (
    get_next_lead_id,
    get_next_conversacion_id,
    guardar_lead_completo_trx,
)

router = APIRouter(tags=["Telegram"])


class TelegramLeadRequest(BaseModel):
    telegram_user_id: str = Field(..., min_length=1)
    nombre: str = Field(..., min_length=1)
    telefono: str | None = None
    mensaje: str = Field(..., min_length=1)


@router.post("/leads/telegram")
def receive_telegram_lead(data: TelegramLeadRequest):
    """
    Recibe un mensaje de Telegram y lo persiste
    utilizando la misma capa transaccional existente.
    """

    ahora = datetime.now(timezone.utc)

    try:
        with get_connection() as conn:

            lead_id = get_next_lead_id(conn)
            conversacion_id = get_next_conversacion_id(conn)

            lead_data = {
                "lead_id": lead_id,
                "registrado_en": ahora,
                "canal": "Telegram",
                "empresa_id": "EMP-01",
                "punto_venta_id": "PV-001",
                "nombre_cliente": data.nombre,
                "telefono": data.telefono,
                "correo": None,
                "ciudad": None,
                "texto_modelo_original": None,
                "sku_motocicleta": None,
                "estado_gestion": "NUEVO",
                "primer_contacto_en": ahora,
                "campana": "Telegram",
            }

            fuente_data = {
                "lead_id": lead_id,
                "archivo_fuente":"telegram_api",
                "fila_fuente": None,
                "canal": "Telegram",
                "referencia_fuente": data.telegram_user_id,
                "campana": "Telegram",
                "creado_fuente_en": ahora,
            }

            conv_data = {
                "conversacion_id": conversacion_id,
                "lead_id": lead_id,
                "canal": "Telegram",
                "iniciada_en": ahora,
            }

            mensajes_data = [
                {
                    "conversacion_id": conversacion_id,
                    "remitente": "cliente",
                    "enviado_en": ahora,
                    "texto": data.mensaje,
                    "orden_mensaje": 1,
                }
            ]

            extraccion_data = {
                "lead_id": lead_id,
                "conversacion_id": conversacion_id,
                "sku_motocicleta": None,
                "pago_inicial": None,
                "metodo_pago": None,
                "intencion_declarada": None,
                "objecion_principal": None,
                "solicita_cotizacion": False,
                "solicita_cita": False,
                "modelo_extraccion": "telegram_mvp",
                "version_extraccion": "1.0",
            }

            result = guardar_lead_completo_trx(
                conn=conn,
                lead_data=lead_data,
                fuente_data=fuente_data,
                conv_data=conv_data,
                mensajes_data=mensajes_data,
                extraccion_data=extraccion_data,
            )

            return {
                "ok": True,
                "lead_id": result["lead_id"],
                "conversacion_id": result["conversacion_id"],
                "estado": "procesado",
            }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando lead de Telegram: {exc}",
        )