from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from database import get_connection
from queries.leads_queries import get_catalogo_motocicletas
from queries.persistence_queries import (
    get_next_lead_id,
    get_next_conversacion_id,
    guardar_lead_completo_trx,
)
from services.extraction_service import extract_motocicleta

router = APIRouter(tags=["Telegram"])


class TelegramLeadRequest(BaseModel):
    telegram_user_id: str = Field(..., min_length=1)
    nombre: str = Field(..., min_length=1)
    telefono: str | None = None
    mensaje: str = Field(..., min_length=1)
    motocicleta: str | None = None
    metodo_pago: str | None = None
    pago_inicial: int | float | None = None
    solicita_cotizacion: bool | None = None
    solicita_cita: bool | None = None
    empresa_id: str = "EMP-01"
    punto_venta_id: str = "PV-001"


@router.post("/leads/telegram")
def receive_telegram_lead(data: TelegramLeadRequest):
    """
    Recibe un lead de Telegram con su ficha comercial completa y lo persiste
    utilizando la capa transaccional existente.
    """
    ahora = datetime.now(timezone.utc)

    try:
        with get_connection() as conn:
            empresa_id = data.empresa_id or "EMP-01"
            punto_venta_id = data.punto_venta_id or "PV-001"

            # Validar relación empresa y punto de venta
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM core.puntos_venta
                    WHERE punto_venta_id = %s AND empresa_id = %s AND activo = TRUE;
                    """,
                    (punto_venta_id, empresa_id),
                )
                if not cur.fetchone():
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"La combinación de empresa_id '{empresa_id}' y "
                            f"punto_venta_id '{punto_venta_id}' no es válida o está inactiva."
                        ),
                    )

            # Homologación del SKU utilizando el catálogo existente
            catalogo = get_catalogo_motocicletas(conn)
            texto_modelo_original = data.motocicleta.strip() if data.motocicleta else None
            sku_motocicleta = None

            if texto_modelo_original:
                # Comprobar si ya viene como SKU directo
                for moto in catalogo:
                    if moto.get("sku", "").upper() == texto_modelo_original.upper():
                        sku_motocicleta = moto["sku"]
                        break

                # Si no es SKU directo, usar la lógica de extracción existente
                if not sku_motocicleta:
                    sku_motocicleta = extract_motocicleta(
                        [{"role": "user", "content": texto_modelo_original}],
                        catalogo,
                    )

            # Fallback: intentar extraer del texto del mensaje si no se detectó
            if not sku_motocicleta and data.mensaje:
                sku_motocicleta = extract_motocicleta(
                    [{"role": "user", "content": data.mensaje}],
                    catalogo,
                )
                if not texto_modelo_original and sku_motocicleta:
                    texto_modelo_original = sku_motocicleta

            # Normalización del método de pago según el estándar del proyecto
            metodo_pago_norm = None
            if data.metodo_pago:
                m_str = data.metodo_pago.strip()
                m_lower = m_str.lower()
                if m_lower in ("credito", "crédito", "financiado", "financiada", "financiación"):
                    metodo_pago_norm = "Crédito"
                elif m_lower in ("contado", "efectivo", "de contado"):
                    metodo_pago_norm = "Contado"
                else:
                    metodo_pago_norm = m_str

            # Pago inicial: Solo aplica para crédito; contado no inventa cuota inicial
            pago_inicial_val = None
            if metodo_pago_norm == "Crédito" and data.pago_inicial is not None:
                try:
                    pago_inicial_val = int(data.pago_inicial)
                except (ValueError, TypeError):
                    pago_inicial_val = None

            lead_id = get_next_lead_id(conn)
            conversacion_id = get_next_conversacion_id(conn)

            lead_data = {
                "lead_id": lead_id,
                "registrado_en": ahora,
                "canal": "Telegram",
                "empresa_id": empresa_id,
                "punto_venta_id": punto_venta_id,
                "nombre_cliente": data.nombre,
                "telefono": data.telefono,
                "correo": None,
                "ciudad": None,
                "texto_modelo_original": texto_modelo_original,
                "sku_motocicleta": sku_motocicleta,
                "estado_gestion": "NUEVO",
                "primer_contacto_en": ahora,
                "campana": "Telegram",
            }

            fuente_data = {
                "lead_id": lead_id,
                "archivo_fuente": "telegram_api",
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

            intencion = (
                "Compra"
                if (sku_motocicleta or data.solicita_cotizacion or data.solicita_cita or metodo_pago_norm)
                else None
            )

            extraccion_data = {
                "lead_id": lead_id,
                "conversacion_id": conversacion_id,
                "sku_motocicleta": sku_motocicleta,
                "pago_inicial": pago_inicial_val,
                "metodo_pago": metodo_pago_norm,
                "intencion_declarada": intencion,
                "objecion_principal": None,
                "solicita_cotizacion": data.solicita_cotizacion,
                "solicita_cita": data.solicita_cita,
                "modelo_extraccion": "telegram_bot",
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

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando lead de Telegram: {exc}",
        )