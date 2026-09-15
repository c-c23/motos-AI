"""
queries/dashboard_queries.py
-----------------------------
Consultas SQL para el dashboard de indicadores del CRM.
Todas las funciones reciben una conexión activa (psycopg.Connection).
"""

from __future__ import annotations
import psycopg
from psycopg.rows import dict_row


def get_kpis(conn: psycopg.Connection) -> dict:
    """
    Devuelve los KPIs principales del dashboard:
    - total_leads
    - leads_asignados
    - leads_sin_asignar
    - leads_calientes
    - leads_tibios
    - leads_frios
    - leads_nuevos
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                COUNT(*)                                        AS total_leads,
                COUNT(asesor_id)                               AS leads_asignados,
                COUNT(*) FILTER (WHERE asesor_id IS NULL)      AS leads_sin_asignar,
                COUNT(*) FILTER (WHERE temperatura = 'Caliente') AS leads_calientes,
                COUNT(*) FILTER (WHERE temperatura = 'Tibio')    AS leads_tibios,
                COUNT(*) FILTER (WHERE temperatura = 'Frio'
                                    OR temperatura IS NULL)    AS leads_frios,
                COUNT(*) FILTER (WHERE estado_gestion = 'Nuevo') AS leads_nuevos
            FROM core.vw_leads_gestion;
        """)
        row = cur.fetchone()
        return {
            "total_leads":       int(row[0]),
            "leads_asignados":   int(row[1]),
            "leads_sin_asignar": int(row[2]),
            "leads_calientes":   int(row[3]),
            "leads_tibios":      int(row[4]),
            "leads_frios":       int(row[5]),
            "leads_nuevos":      int(row[6]),
        }


def get_leads_por_canal(conn: psycopg.Connection) -> list[dict]:
    """
    Cuenta de leads agrupados por canal de origen.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT
                COALESCE(canal, 'Sin canal') AS canal,
                COUNT(*) AS total
            FROM core.vw_leads_gestion
            GROUP BY canal
            ORDER BY total DESC;
        """)
        return cur.fetchall()


def get_leads_por_temperatura(conn: psycopg.Connection) -> list[dict]:
    """
    Cuenta de leads agrupados por temperatura de scoring.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT
                COALESCE(temperatura, 'Sin score') AS temperatura,
                COUNT(*) AS total
            FROM core.vw_leads_gestion
            GROUP BY temperatura
            ORDER BY total DESC;
        """)
        return cur.fetchall()


def get_leads_por_asesor(conn: psycopg.Connection) -> list[dict]:
    """
    Cuenta de leads por asesor asignado.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT
                COALESCE(asesor, 'Sin asignar') AS asesor,
                COUNT(*) AS total
            FROM core.vw_leads_gestion
            GROUP BY asesor
            ORDER BY total DESC;
        """)
        return cur.fetchall()


def get_leads_por_empresa(conn: psycopg.Connection) -> list[dict]:
    """
    Cuenta de leads por empresa.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT
                COALESCE(empresa, 'Sin empresa') AS empresa,
                COUNT(*) AS total
            FROM core.vw_leads_gestion
            GROUP BY empresa
            ORDER BY total DESC;
        """)
        return cur.fetchall()


def get_distribucion_prioridad(conn: psycopg.Connection) -> list[dict]:
    """
    Devuelve el puntaje de prioridad de todos los leads para graficar distribución.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT
                lead_id,
                nombre_cliente,
                puntaje_prioridad,
                temperatura
            FROM core.vw_leads_gestion
            WHERE puntaje_prioridad IS NOT NULL
            ORDER BY puntaje_prioridad DESC;
        """)
        return cur.fetchall()
