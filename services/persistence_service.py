"""
services/persistence_service.py
--------------------------------
Servicio para coordinar la persistencia de conversaciones simuladas, extracciones y scoring V1 en PostgreSQL.
"""

from datetime import datetime
from database import get_connection
from queries.persistence_queries import (
    get_next_lead_id,
    get_next_conversacion_id,
    guardar_lead_completo_trx,
)
from services.extraction_service import extract_conversation
from services.scoring_service import evaluar_y_guardar_scoring_lead


def guardar_conversacion_simulada(
    messages: list[dict],
    catalogo: list[dict],
    nombre_cliente: str = "Cliente Telegram Simulado",
    telefono: str | None = None,
    empresa_id: str = "EMP-01",
    punto_venta_id: str = "PV-002",
) -> dict:
    """
    Coordina el flujo completo de persistencia atómica y scoring V1:
    1. Ejecuta la extracción estructurada sobre los mensajes.
    2. Genera los IDs únicos secuenciales (LEAD-xxx, CONV-xxx).
    3. Construye los registros para leads, fuentes, conversaciones, mensajes y extracciones.
    4. Ejecuta la transacción SQL de la Fase 3 en PostgreSQL.
    5. Ejecuta de forma independiente el scoring V1 y lo persiste en PostgreSQL.

    Args:
        messages: Lista de mensajes de la sesión simulada.
        catalogo: Catálogo activo de motocicletas.
        nombre_cliente: Nombre asignado al lead simulado.
        telefono: Teléfono asignado (si no se provee, se genera uno basado en el ID).
        empresa_id: ID de empresa en PostgreSQL.
        punto_venta_id: ID de punto de venta en PostgreSQL.

    Returns:
        dict con 'lead_id', 'conversacion_id', 'extraccion' y 'scoring'.
    """
    if not messages:
        raise ValueError("No se puede guardar una conversación sin mensajes.")

    # 1. Obtener la extracción estructurada actual
    extraccion = extract_conversation(messages, catalogo)

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
            "ciudad": "Armenia",
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

        extraccion_data = {
            "lead_id": lead_id,
            "conversacion_id": conv_id,
            "sku_motocicleta": extraccion.get("sku_motocicleta"),
            "pago_inicial": extraccion.get("pago_inicial"),
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

    # 5. Ejecutar scoring V1 de forma desacoplada
    try:
        res_scoring = evaluar_y_guardar_scoring_lead(conn=None, lead_id=lead_id)
        res["scoring"] = res_scoring
    except Exception as e:
        res["scoring_error"] = str(e)

    return res
