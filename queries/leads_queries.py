"""
queries/leads_queries.py
------------------------
Consultas SQL relacionadas con leads.
Todas las funciones reciben una conexión activa (psycopg.Connection)
y devuelven listas de diccionarios o un solo diccionario.
"""

from __future__ import annotations
import psycopg
from psycopg.rows import dict_row


def get_leads(conn: psycopg.Connection) -> list[dict]:
    """
    Lee todos los leads desde vw_leads_gestion, ordenados por prioridad desc.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT
                lead_id,
                nombre_cliente,
                telefono,
                correo,
                ciudad,
                canal,
                campana,
                empresa_id,
                empresa,
                punto_venta_id,
                punto_venta,
                sku_motocicleta,
                marca,
                linea,
                cilindraje_cc,
                segmento,
                precio_lista,
                pago_inicial,
                metodo_pago,
                intencion_declarada,
                objecion_principal,
                solicita_cotizacion,
                solicita_cita,
                probabilidad_comercial,
                puntaje_urgencia,
                puntaje_prioridad,
                temperatura,
                asesor_id,
                asesor,
                estado_gestion,
                primer_contacto_en,
                registrado_en,
                actualizado_en
            FROM core.vw_leads_gestion
            ORDER BY puntaje_prioridad DESC NULLS LAST;
        """)
        return cur.fetchall()


def get_lead_by_id(conn: psycopg.Connection, lead_id: str) -> dict | None:
    """
    Lee un lead completo desde vw_leads_gestion por su lead_id.
    Devuelve None si no existe.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT *
            FROM core.vw_leads_gestion
            WHERE lead_id = %s;
        """, (lead_id,))
        return cur.fetchone()


def get_mensajes_lead(conn: psycopg.Connection, lead_id: str) -> list[dict]:
    """
    Lee todos los mensajes asociados a un lead, ordenados cronológicamente.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT
                m.mensaje_id,
                m.conversacion_id,
                m.remitente,
                m.enviado_en,
                m.texto,
                m.orden_mensaje,
                c.canal
            FROM core.mensajes m
            JOIN core.conversaciones c ON m.conversacion_id = c.conversacion_id
            WHERE c.lead_id = %s
            ORDER BY m.orden_mensaje ASC;
        """, (lead_id,))
        return cur.fetchall()


def get_eventos_lead(conn: psycopg.Connection, lead_id: str) -> list[dict]:
    """
    Lee el historial de eventos de gestión de un lead, en orden cronológico.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT
                eg.evento_id,
                eg.tipo_evento,
                eg.fecha_evento,
                eg.asesor_id,
                asr.nombre AS asesor,
                eg.metadatos
            FROM core.eventos_gestion eg
            LEFT JOIN core.asesores asr ON eg.asesor_id = asr.asesor_id
            WHERE eg.lead_id = %s
            ORDER BY eg.fecha_evento ASC;
        """, (lead_id,))
        return cur.fetchall()


def get_extracciones_lead(conn: psycopg.Connection, lead_id: str) -> dict | None:
    """
    Lee la extracción de IA más reciente de un lead.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT *
            FROM core.extracciones_ia
            WHERE lead_id = %s
            ORDER BY extraido_en DESC
            LIMIT 1;
        """, (lead_id,))
        return cur.fetchone()


def get_puntaje_lead(conn: psycopg.Connection, lead_id: str) -> dict | None:
    """
    Lee el puntaje actual del lead.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT *
            FROM core.puntajes_leads
            WHERE lead_id = %s AND es_actual = TRUE
            LIMIT 1;
        """, (lead_id,))
        return cur.fetchone()


def get_valores_filtros(conn: psycopg.Connection) -> dict:
    """
    Lee los valores únicos disponibles para los filtros del CRM.
    Devuelve listas de: canales, temperaturas, empresas, puntos_venta, asesores, estados.
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT canal FROM core.vw_leads_gestion
            WHERE canal IS NOT NULL ORDER BY canal;
        """)
        canales = [r[0] for r in cur.fetchall()]

        cur.execute("""
            SELECT DISTINCT temperatura FROM core.vw_leads_gestion
            WHERE temperatura IS NOT NULL ORDER BY temperatura;
        """)
        temperaturas = [r[0] for r in cur.fetchall()]

        cur.execute("""
            SELECT DISTINCT empresa FROM core.vw_leads_gestion
            WHERE empresa IS NOT NULL ORDER BY empresa;
        """)
        empresas = [r[0] for r in cur.fetchall()]

        cur.execute("""
            SELECT DISTINCT punto_venta FROM core.vw_leads_gestion
            WHERE punto_venta IS NOT NULL ORDER BY punto_venta;
        """)
        puntos_venta = [r[0] for r in cur.fetchall()]

        cur.execute("""
            SELECT DISTINCT asesor FROM core.vw_leads_gestion
            WHERE asesor IS NOT NULL ORDER BY asesor;
        """)
        asesores = [r[0] for r in cur.fetchall()]

        cur.execute("""
            SELECT DISTINCT estado_gestion FROM core.vw_leads_gestion
            WHERE estado_gestion IS NOT NULL ORDER BY estado_gestion;
        """)
        estados = [r[0] for r in cur.fetchall()]

    return {
        "canales": canales,
        "temperaturas": temperaturas,
        "empresas": empresas,
        "puntos_venta": puntos_venta,
        "asesores": asesores,
        "estados": estados,
    }


def get_catalogo_motocicletas(conn: psycopg.Connection) -> list[dict]:
    """
    Lee todas las motocicletas activas para la matching/extracción de modelos.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT sku, marca, linea, cilindraje_cc, segmento, precio_lista
            FROM core.motocicletas
            WHERE activo = TRUE
            ORDER BY sku;
        """)
        return cur.fetchall()

