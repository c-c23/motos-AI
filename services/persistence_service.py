"""
services/persistence_service.py
--------------------------------
Servicio para coordinar la persistencia de conversaciones simuladas, extracciones y scoring V1 en PostgreSQL.
"""

import logging
from datetime import datetime
from database import get_connection
from queries.persistence_queries import (
    get_next_lead_id,
    get_next_conversacion_id,
    guardar_lead_completo_trx,
)
from services.extraction_service import extract_conversation
from services.scoring_service import (
    evaluar_y_guardar_scoring_lead,
    evaluar_y_guardar_scoring_v2_lead,
)

logger = logging.getLogger("services.persistence_service")


def guardar_conversacion_simulada(
    messages: list[dict],
    catalogo: list[dict],
    nombre_cliente: str = "Cliente Telegram Simulado",
    telefono: str | None = None,
    empresa_id: str = "EMP-01",
    punto_venta_id: str = "PV-002",
    extraccion_override: dict | None = None,
) -> dict:
    """
    Coordina el flujo completo de persistencia atómica y scoring V1:
    1. Ejecuta la extracción estructurada sobre los mensajes (o usa extraccion_override).
    2. Genera los IDs únicos secuenciales (LEAD-xxx, CONV-xxx).
    3. Construye los registros para leads, fuentes, conversaciones, mensajes y extracciones.
    4. Ejecuta la transacción SQL de la Fase 3 en PostgreSQL.
    5. Ejecuta de forma independiente el scoring V1 y lo persiste en PostgreSQL.
    """
    if not messages:
        raise ValueError("No se puede guardar una conversación sin mensajes.")

    # 1. Obtener la extracción estructurada actual
    raw_ext = extract_conversation(messages, catalogo)
    extraccion = extraccion_override or raw_ext

    ahora = datetime.now()

    with get_connection() as conn:
        # 2. Generar IDs atómicos
        lead_id = get_next_lead_id(conn)
        conv_id = get_next_conversacion_id(conn)

        num_id = lead_id.split("-")[1] if "-" in lead_id else "006"
        tel = telefono or f"+57300000{num_id}"

        # 3. Preparar payloads
        lead_data = {
            "lead_id": lead_id,
            "registrado_en": ahora,
            "canal": "Telegram",
            "empresa_id": empresa_id,
            "punto_venta_id": punto_venta_id,
            "nombre_cliente": nombre_cliente,
            "telefono": tel,
            "correo": None,
            "ciudad": extraccion.get("ciudad_sede") or "Armenia",
            "texto_modelo_original": extraccion.get("sku_motocicleta"),
            "sku_motocicleta": extraccion.get("sku_motocicleta"),
            "estado_gestion": "Nuevo",
            "primer_contacto_en": None,  # No contactado aún por asesor
            "campana": "Simulador Telegram",
        }

        fuente_data = {
            "lead_id": lead_id,
            "archivo_fuente": "simulador_telegram",
            "fila_fuente": None,
            "canal": "Telegram",
            "referencia_fuente": "SIM-TELEGRAM",
            "campana": "Simulador Telegram",
            "creado_fuente_en": ahora,
        }

        conv_data = {
            "conversacion_id": conv_id,
            "lead_id": lead_id,
            "canal": "Telegram",
            "iniciada_en": ahora,
        }

        mensajes_data = []
        for idx, msg in enumerate(messages, start=1):
            role_raw = msg.get("role") or msg.get("remitente", "")
            remitente = "Cliente" if role_raw.lower() in ("user", "cliente") else "Bot"
            mensajes_data.append({
                "conversacion_id": conv_id,
                "remitente": remitente,
                "enviado_en": ahora,
                "texto": msg.get("content") or msg.get("texto") or "",
                "orden_mensaje": idx,
            })

        pago_inicial_val = extraccion.get("pago_inicial")
        pago_inicial_sql = pago_inicial_val if isinstance(pago_inicial_val, (int, float)) else None

        extraccion_data = {
            "lead_id": lead_id,
            "conversacion_id": conv_id,
            "sku_motocicleta": extraccion.get("sku_motocicleta"),
            "pago_inicial": pago_inicial_sql,
            "metodo_pago": extraccion.get("metodo_pago"),
            "intencion_declarada": extraccion.get("intencion_declarada"),
            "objecion_principal": None,
            "solicita_cotizacion": extraccion.get("solicita_cotizacion"),
            "solicita_cita": extraccion.get("solicita_cita"),
            "modelo_extraccion": "reglas",
            "version_extraccion": "v1.0",
        }

        # 4. Ejecutar transacción Fase 3
        res = guardar_lead_completo_trx(
            conn, lead_data, fuente_data, conv_data, mensajes_data, extraccion_data
        )

    res["extraccion"] = extraccion

    # 5. Ejecutar scoring V1 base de forma desacoplada (garantiza histórico V1)
    try:
        res_scoring_v1 = evaluar_y_guardar_scoring_lead(conn=None, lead_id=lead_id)
        res["scoring_v1"] = res_scoring_v1
        res["scoring"] = res_scoring_v1  # Base por defecto si V2 no pudiera ejecutarse
    except Exception as e:
        logger.warning("Error calculando scoring V1 para %s: %s", lead_id, e)
        res["scoring_v1_error"] = str(e)

    # 6. Ejecutar scoring V2 híbrido (Gemini / fallback reglas) desacoplado
    try:
        res_scoring_v2 = evaluar_y_guardar_scoring_v2_lead(
            conn=None,
            lead_id=lead_id,
            mensajes=messages,
            catalogo=catalogo,
        )
        res["scoring_v2"] = res_scoring_v2
        res["scoring"] = res_scoring_v2  # Score activo V2 para la UI y dashboard
    except Exception as e:
        logger.error("Error calculando scoring V2 para %s: %s", lead_id, e)
        res["scoring_v2_error"] = str(e)

    return res
