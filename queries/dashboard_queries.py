"""
queries/dashboard_queries.py
-----------------------------
Consultas SQL agregadas para el dashboard de indicadores del CRM.
PostgreSQL es la fuente de verdad: no recalcula scoring ni asignación.
Todas las funciones reciben una conexión activa (psycopg.Connection).
"""

from __future__ import annotations
import psycopg
from psycopg.rows import dict_row

# Estados que se consideran pendientes de gestión comercial (dato almacenado).
SQL_PENDIENTES_GESTION = """
    LOWER(TRIM(COALESCE(l.estado_gestion, ''))) IN ('sin gestion', 'sin gestión', 'nuevo')
"""


def _filtro_empresa(empresa_id: str | None) -> tuple[str, list]:
    if empresa_id:
        return " AND l.empresa_id = %s", [empresa_id]
    return "", []


def get_kpis(conn: psycopg.Connection, empresa_id: str | None = None) -> dict:
    """
    KPIs operativos agregados en PostgreSQL (sin traer la tabla completa).
    """
    extra, params = _filtro_empresa(empresa_id)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                COUNT(*) AS total_leads,
                COUNT(*) FILTER (WHERE {SQL_PENDIENTES_GESTION}) AS leads_pendientes_gestion,
                COUNT(a.asesor_id) AS leads_asignados,
                COUNT(*) FILTER (WHERE a.asesor_id IS NULL) AS leads_sin_asignar,
                COUNT(*) FILTER (WHERE p.temperatura = 'Crítico') AS leads_criticos,
                COUNT(*) FILTER (WHERE p.temperatura = 'Alto') AS leads_altos,
                COUNT(*) FILTER (WHERE p.temperatura = 'Medio') AS leads_medios,
                COUNT(*) FILTER (WHERE p.temperatura = 'Bajo') AS leads_bajos,
                COUNT(*) FILTER (WHERE LOWER(TRIM(COALESCE(l.estado_gestion, ''))) = 'nuevo') AS leads_nuevos,
                AVG(p.puntaje_prioridad) FILTER (WHERE p.puntaje_prioridad IS NOT NULL) AS promedio_prioridad
            FROM core.leads l
            LEFT JOIN core.puntajes_leads p
                ON l.lead_id = p.lead_id AND p.es_actual = TRUE
            LEFT JOIN core.asignaciones a
                ON l.lead_id = a.lead_id AND a.es_actual = TRUE
            WHERE TRUE
            {extra}
            """,
            params,
        )
        row = cur.fetchone()
        prom = float(row[9]) if row[9] is not None else 0.0
        return {
            "total_leads": int(row[0]),
            "leads_pendientes_gestion": int(row[1]),
            "leads_asignados": int(row[2]),
            "leads_sin_asignar": int(row[3]),
            "leads_criticos": int(row[4]),
            "leads_altos": int(row[5]),
            "leads_medios": int(row[6]),
            "leads_bajos": int(row[7]),
            "leads_nuevos": int(row[8]),
            "promedio_prioridad": round(prom, 2),
            # Compatibilidad con la página de inicio previa
            "leads_calientes": int(row[4]) + int(row[5]),
            "leads_tibios": int(row[6]),
            "leads_frios": int(row[7]),
        }


def get_conteos_sistema(conn: psycopg.Connection) -> dict:
    """
    Conteos de dimensiones y persistencia operativa para validar el dashboard
    contra PostgreSQL. No expone credenciales.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM core.leads) AS total_leads,
                (SELECT COUNT(*) FROM core.puntajes_leads WHERE es_actual = TRUE) AS scores_activos,
                (SELECT COUNT(*) FROM core.asignaciones) AS asignaciones,
                (SELECT COUNT(*) FROM core.asignaciones WHERE es_actual = TRUE) AS asignaciones_activas,
                (SELECT COUNT(*) FROM core.asignaciones WHERE es_actual = TRUE AND lead_id LIKE 'LD-%') AS asignaciones_reales,
                (SELECT COUNT(*) FROM core.asignaciones WHERE es_actual = TRUE AND lead_id LIKE 'LEAD-%') AS asignaciones_sinteticas,
                (SELECT COUNT(*) FROM core.leads l
                 LEFT JOIN core.asignaciones a ON l.lead_id = a.lead_id AND a.es_actual = TRUE
                 WHERE a.asignacion_id IS NULL) AS leads_sin_asignacion,
                (SELECT COUNT(*) FROM core.asesores) AS asesores,
                (SELECT COUNT(*) FROM core.asesores WHERE activo = TRUE) AS asesores_activos,
                (SELECT COUNT(*) FROM core.asesores WHERE activo = FALSE) AS asesores_inactivos,
                (SELECT COUNT(*) FROM core.empresas) AS empresas,
                (SELECT COUNT(*) FROM core.puntos_venta) AS puntos_venta
            """
        )
        row = cur.fetchone()
        return {
            "total_leads": int(row[0]),
            "scores_activos": int(row[1]),
            "asignaciones": int(row[2]),
            "asignaciones_activas": int(row[3]),
            "asignaciones_reales": int(row[4]),
            "asignaciones_sinteticas": int(row[5]),
            "leads_sin_asignacion": int(row[6]),
            "asesores": int(row[7]),
            "asesores_activos": int(row[8]),
            "asesores_inactivos": int(row[9]),
            "empresas": int(row[10]),
            "puntos_venta": int(row[11]),
        }


def get_leads_por_canal(conn: psycopg.Connection, empresa_id: str | None = None) -> list[dict]:
    extra, params = _filtro_empresa(empresa_id)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            SELECT
                COALESCE(l.canal, 'Sin canal') AS canal,
                COUNT(*) AS total
            FROM core.leads l
            WHERE TRUE
            {extra}
            GROUP BY l.canal
            ORDER BY total DESC
            """,
            params,
        )
        return cur.fetchall()


def get_leads_por_temperatura(conn: psycopg.Connection, empresa_id: str | None = None) -> list[dict]:
    extra, params = _filtro_empresa(empresa_id)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            SELECT
                COALESCE(p.temperatura, 'Sin score') AS temperatura,
                COUNT(*) AS total
            FROM core.leads l
            LEFT JOIN core.puntajes_leads p
                ON l.lead_id = p.lead_id AND p.es_actual = TRUE
            WHERE TRUE
            {extra}
            GROUP BY p.temperatura
            ORDER BY
                CASE COALESCE(p.temperatura, 'Sin score')
                    WHEN 'Crítico' THEN 1
                    WHEN 'Alto' THEN 2
                    WHEN 'Medio' THEN 3
                    WHEN 'Bajo' THEN 4
                    ELSE 5
                END
            """,
            params,
        )
        return cur.fetchall()


def get_leads_por_asesor(conn: psycopg.Connection, empresa_id: str | None = None) -> list[dict]:
    extra, params = _filtro_empresa(empresa_id)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            SELECT
                COALESCE(emp.nombre, l.empresa_id, 'Sin empresa') AS empresa,
                COALESCE(asr.nombre, 'Sin asignar') AS asesor,
                COUNT(*) AS total
            FROM core.leads l
            LEFT JOIN core.empresas emp ON l.empresa_id = emp.empresa_id
            LEFT JOIN core.asignaciones a
                ON l.lead_id = a.lead_id AND a.es_actual = TRUE
            LEFT JOIN core.asesores asr ON a.asesor_id = asr.asesor_id
            WHERE TRUE
            {extra}
            GROUP BY emp.nombre, l.empresa_id, asr.nombre
            ORDER BY total DESC
            """,
            params,
        )
        return cur.fetchall()


def get_leads_por_empresa(conn: psycopg.Connection, empresa_id: str | None = None) -> list[dict]:
    extra, params = _filtro_empresa(empresa_id)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            SELECT
                COALESCE(emp.nombre, l.empresa_id, 'Sin empresa') AS empresa,
                l.empresa_id,
                COUNT(*) AS total
            FROM core.leads l
            LEFT JOIN core.empresas emp ON l.empresa_id = emp.empresa_id
            WHERE TRUE
            {extra}
            GROUP BY emp.nombre, l.empresa_id
            ORDER BY total DESC
            """,
            params,
        )
        return cur.fetchall()


def get_leads_por_punto_venta(conn: psycopg.Connection, empresa_id: str | None = None) -> list[dict]:
    extra, params = _filtro_empresa(empresa_id)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            SELECT
                COALESCE(emp.nombre, l.empresa_id, 'Sin empresa') AS empresa,
                COALESCE(pv.nombre, l.punto_venta_id, 'Sin punto de venta') AS punto_venta,
                l.punto_venta_id,
                COUNT(*) AS total
            FROM core.leads l
            LEFT JOIN core.empresas emp ON l.empresa_id = emp.empresa_id
            LEFT JOIN core.puntos_venta pv ON l.punto_venta_id = pv.punto_venta_id
            WHERE TRUE
            {extra}
            GROUP BY emp.nombre, l.empresa_id, pv.nombre, l.punto_venta_id
            ORDER BY empresa, total DESC
            """,
            params,
        )
        return cur.fetchall()


def get_leads_por_estado_gestion(conn: psycopg.Connection, empresa_id: str | None = None) -> list[dict]:
    extra, params = _filtro_empresa(empresa_id)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            SELECT
                COALESCE(l.estado_gestion, 'Sin estado') AS estado_gestion,
                COUNT(*) AS total
            FROM core.leads l
            WHERE TRUE
            {extra}
            GROUP BY l.estado_gestion
            ORDER BY total DESC
            """,
            params,
        )
        return cur.fetchall()


def get_leads_asignados_vs_no(conn: psycopg.Connection, empresa_id: str | None = None) -> list[dict]:
    extra, params = _filtro_empresa(empresa_id)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            SELECT
                CASE WHEN a.asesor_id IS NOT NULL THEN 'ASIGNADO' ELSE 'SIN ASIGNAR' END AS estado_asignacion,
                COUNT(*) AS total
            FROM core.leads l
            LEFT JOIN core.asignaciones a
                ON l.lead_id = a.lead_id AND a.es_actual = TRUE
            WHERE TRUE
            {extra}
            GROUP BY CASE WHEN a.asesor_id IS NOT NULL THEN 'ASIGNADO' ELSE 'SIN ASIGNAR' END
            ORDER BY estado_asignacion
            """,
            params,
        )
        return cur.fetchall()


def get_distribucion_prioridad(
    conn: psycopg.Connection,
    empresa_id: str | None = None,
    limite: int = 50,
) -> list[dict]:
    """
    Ranking de prioridad (solo lectura). No recalcula scores.
    """
    extra, params = _filtro_empresa(empresa_id)
    params.append(limite)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            SELECT
                l.lead_id,
                l.nombre_cliente,
                COALESCE(emp.nombre, l.empresa_id) AS empresa,
                p.puntaje_prioridad,
                p.temperatura
            FROM core.leads l
            LEFT JOIN core.empresas emp ON l.empresa_id = emp.empresa_id
            LEFT JOIN core.puntajes_leads p
                ON l.lead_id = p.lead_id AND p.es_actual = TRUE
            WHERE p.puntaje_prioridad IS NOT NULL
            {extra}
            ORDER BY p.puntaje_prioridad DESC NULLS LAST,
                     p.puntaje_urgencia DESC NULLS LAST,
                     l.registrado_en ASC NULLS LAST
            LIMIT %s
            """,
            params,
        )
        return cur.fetchall()
