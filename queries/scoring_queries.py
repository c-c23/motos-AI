"""
queries/scoring_queries.py
---------------------------
Consultas SQL y operaciones transaccionales de persistencia para el scoring V1 de leads.
Todas las funciones reciben una conexión activa (psycopg.Connection).
"""

from __future__ import annotations
import json
from datetime import datetime
import psycopg
from psycopg.rows import dict_row


def get_lead_data_for_scoring(conn: psycopg.Connection, lead_id: str) -> dict | None:
    """
    Obtiene los datos relevantes del lead y su extracción más reciente
    para calcular el scoring de prioridad V1.

    Args:
        conn: Conexión activa a PostgreSQL.
        lead_id: Identificador del lead.

    Returns:
        dict con los datos del lead o None si no existe el lead.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT
                l.lead_id,
                l.registrado_en,
                l.primer_contacto_en,
                e.solicita_cita,
                e.pago_inicial,
                e.metodo_pago,
                e.intencion_declarada
            FROM core.leads l
            LEFT JOIN (
                SELECT DISTINCT ON (lead_id)
                    lead_id,
                    solicita_cita,
                    pago_inicial,
                    metodo_pago,
                    intencion_declarada
                FROM core.extracciones_ia
                WHERE lead_id = %s
                ORDER BY lead_id, extraido_en DESC
            ) e ON l.lead_id = e.lead_id
            WHERE l.lead_id = %s;
        """, (lead_id, lead_id))
        return cur.fetchone()


def guardar_puntaje_lead_trx(conn: psycopg.Connection, puntaje_data: dict) -> dict:
    """
    Guarda un nuevo score de prioridad en core.puntajes_leads manteniendo la
    regla de integridad: exactamente un registro con es_actual = TRUE por lead_id.

    Operación realizada dentro de una transacción explícita (BEGIN...COMMIT/ROLLBACK).

    Args:
        conn: Conexión activa a PostgreSQL.
        puntaje_data: Diccionario con las llaves requeridas.

    Returns:
        dict con la confirmación de la inserción y los campos guardados.
    """
    lead_id = puntaje_data["lead_id"]
    razones = puntaje_data.get("razones", {})
    razones_json = json.dumps(razones) if isinstance(razones, dict) else razones

    data = {
        "lead_id": lead_id,
        "probabilidad_comercial": puntaje_data.get("probabilidad_comercial"),
        "puntaje_urgencia": puntaje_data.get("puntaje_urgencia"),
        "puntaje_prioridad": puntaje_data.get("puntaje_prioridad"),
        "temperatura": puntaje_data.get("temperatura"),
        "modelo_scoring": puntaje_data.get("modelo_scoring", "reglas_prioridad"),
        "version_scoring": puntaje_data.get("version_scoring", "v1.0"),
        "razones": razones_json,
        "puntuado_en": puntaje_data.get("puntuado_en", datetime.now()),
    }

    with conn.transaction():
        with conn.cursor() as cur:
            # 1. Desmarcar score actual anterior si existe
            cur.execute("""
                UPDATE core.puntajes_leads
                SET es_actual = FALSE
                WHERE lead_id = %s AND es_actual = TRUE;
            """, (lead_id,))

            # 2. Insertar nuevo score como actual
            cur.execute("""
                INSERT INTO core.puntajes_leads (
                    lead_id,
                    probabilidad_comercial,
                    puntaje_urgencia,
                    puntaje_prioridad,
                    temperatura,
                    modelo_scoring,
                    version_scoring,
                    razones,
                    puntuado_en,
                    es_actual
                ) VALUES (
                    %(lead_id)s,
                    %(probabilidad_comercial)s,
                    %(puntaje_urgencia)s,
                    %(puntaje_prioridad)s,
                    %(temperatura)s,
                    %(modelo_scoring)s,
                    %(version_scoring)s,
                    %(razones)s,
                    %(puntuado_en)s,
                    TRUE
                );
            """, data)

    return data
