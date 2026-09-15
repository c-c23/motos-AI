"""
queries/persistence_queries.py
--------------------------------
Consultas SQL y operaciones transaccionales de persistencia para nuevos leads y conversaciones.
"""

from __future__ import annotations
from datetime import datetime
import psycopg
from psycopg.rows import dict_row


def get_next_lead_id(conn: psycopg.Connection) -> str:
    """
    Genera el siguiente lead_id secuencial (ej. LEAD-006).
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT lead_id FROM core.leads
            WHERE lead_id LIKE 'LEAD-%'
            ORDER BY lead_id DESC
            LIMIT 1;
        """)
        row = cur.fetchone()
        if not row:
            return "LEAD-001"
        try:
            ultimo_num = int(row[0].split("-")[1])
            return f"LEAD-{ultimo_num + 1:03d}"
        except Exception:
            return f"LEAD-{datetime.now().strftime('%M%S')}"


def get_next_conversacion_id(conn: psycopg.Connection) -> str:
    """
    Genera el siguiente conversacion_id secuencial (ej. CONV-006).
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT conversacion_id FROM core.conversaciones
            WHERE conversacion_id LIKE 'CONV-%'
            ORDER BY conversacion_id DESC
            LIMIT 1;
        """)
        row = cur.fetchone()
        if not row:
            return "CONV-001"
        try:
            ultimo_num = int(row[0].split("-")[1])
            return f"CONV-{ultimo_num + 1:03d}"
        except Exception:
            return f"CONV-{datetime.now().strftime('%M%S')}"


def guardar_lead_completo_trx(
    conn: psycopg.Connection,
    lead_data: dict,
    fuente_data: dict,
    conv_data: dict,
    mensajes_data: list[dict],
    extraccion_data: dict,
) -> dict:
    """
    Ejecuta la persistencia atómica en una única transacción PostgreSQL (BEGIN...COMMIT/ROLLBACK).

    Guarda en orden:
    1. core.leads
    2. core.fuentes_leads
    3. core.conversaciones
    4. core.mensajes
    5. core.extracciones_ia

    Returns:
        dict con los IDs creados: {'lead_id': str, 'conversacion_id': str}
    """
    with conn.transaction():
        with conn.cursor() as cur:
            # 1. Insertar Lead
            cur.execute("""
                INSERT INTO core.leads (
                    lead_id, registrado_en, canal, empresa_id, punto_venta_id,
                    nombre_cliente, telefono, correo, ciudad, texto_modelo_original,
                    sku_motocicleta, estado_gestion, primer_contacto_en, campana
                ) VALUES (
                    %(lead_id)s, %(registrado_en)s, %(canal)s, %(empresa_id)s, %(punto_venta_id)s,
                    %(nombre_cliente)s, %(telefono)s, %(correo)s, %(ciudad)s, %(texto_modelo_original)s,
                    %(sku_motocicleta)s, %(estado_gestion)s, %(primer_contacto_en)s, %(campana)s
                );
            """, lead_data)

            # 2. Insertar Fuente
            cur.execute("""
                INSERT INTO core.fuentes_leads (
                    lead_id, archivo_fuente, fila_fuente, canal,
                    referencia_fuente, campana, creado_fuente_en
                ) VALUES (
                    %(lead_id)s, %(archivo_fuente)s, %(fila_fuente)s, %(canal)s,
                    %(referencia_fuente)s, %(campana)s, %(creado_fuente_en)s
                );
            """, fuente_data)

            # 3. Insertar Conversación
            cur.execute("""
                INSERT INTO core.conversaciones (
                    conversacion_id, lead_id, canal, iniciada_en
                ) VALUES (
                    %(conversacion_id)s, %(lead_id)s, %(canal)s, %(iniciada_en)s
                );
            """, conv_data)

            # 4. Insertar Mensajes
            for msg in mensajes_data:
                cur.execute("""
                    INSERT INTO core.mensajes (
                        conversacion_id, remitente, enviado_en, texto, orden_mensaje
                    ) VALUES (
                        %(conversacion_id)s, %(remitente)s, %(enviado_en)s, %(texto)s, %(orden_mensaje)s
                    );
                """, msg)

            # 5. Insertar Extracción IA
            cur.execute("""
                INSERT INTO core.extracciones_ia (
                    lead_id, conversacion_id, sku_motocicleta, pago_inicial,
                    metodo_pago, intencion_declarada, objecion_principal,
                    solicita_cotizacion, solicita_cita, modelo_extraccion, version_extraccion
                ) VALUES (
                    %(lead_id)s, %(conversacion_id)s, %(sku_motocicleta)s, %(pago_inicial)s,
                    %(metodo_pago)s, %(intencion_declarada)s, %(objecion_principal)s,
                    %(solicita_cotizacion)s, %(solicita_cita)s, %(modelo_extraccion)s, %(version_extraccion)s
                );
            """, extraccion_data)

    return {
        "lead_id": lead_data["lead_id"],
        "conversacion_id": conv_data["conversacion_id"],
    }
