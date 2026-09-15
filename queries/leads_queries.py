"""
queries/leads_queries.py
------------------------
Consultas SQL relacionadas con leads para el CRM Motos AI Leads.
Capa de datos de solo lectura para la bandeja y la ficha de detalle.
No recalcula scoring ni asignación.
"""

from __future__ import annotations
import json
import psycopg
from psycopg.rows import dict_row

SQL_ESTADO_GESTION_NORMALIZADO = """
    CASE
        WHEN LOWER(TRIM(l.estado_gestion)) IN ('sin gestion', 'sin gestión') THEN 'Sin gestión'
        WHEN LOWER(TRIM(l.estado_gestion)) = 'contactado' THEN 'Contactado'
        WHEN LOWER(TRIM(l.estado_gestion)) = 'no contesta' THEN 'No contesta'
        WHEN LOWER(TRIM(l.estado_gestion)) IN ('cotización enviada', 'cotizacion enviada') THEN 'Cotización enviada'
        WHEN LOWER(TRIM(l.estado_gestion)) = 'en proceso' THEN 'En proceso'
        WHEN LOWER(TRIM(l.estado_gestion)) = 'descartado' THEN 'Descartado'
        ELSE INITCAP(TRIM(l.estado_gestion))
    END
"""

SQL_BANDEJA_SELECT = f"""
        SELECT
            l.lead_id,
            l.nombre_cliente,
            l.telefono,
            l.correo,
            l.ciudad,
            l.canal,
            l.campana,
            l.empresa_id,
            emp.nombre AS empresa,
            l.punto_venta_id,
            pv.nombre AS punto_venta,
            l.sku_motocicleta,
            l.texto_modelo_original,
            m.marca,
            m.linea,
            m.cilindraje_cc,
            m.segmento,
            m.precio_lista,
            e.pago_inicial,
            e.metodo_pago,
            e.intencion_declarada,
            e.objecion_principal,
            e.solicita_cotizacion,
            e.solicita_cita,
            e.modelo_extraccion,
            e.version_extraccion,
            e.extraccion_id,
            l.estado_gestion AS estado_gestion,
            l.estado_gestion AS estado_gestion_original,
            {SQL_ESTADO_GESTION_NORMALIZADO} AS estado_gestion_normalizado,
            p.probabilidad_comercial,
            p.puntaje_urgencia,
            p.puntaje_prioridad,
            p.temperatura,
            p.modelo_scoring,
            p.version_scoring,
            p.razones,
            p.puntuado_en AS fecha_calculo_scoring,
            a.asesor_id,
            asr.nombre AS asesor,
            a.asignado_en,
            CASE WHEN a.asesor_id IS NOT NULL THEN 'ASIGNADO' ELSE 'SIN ASIGNAR' END AS estado_asignacion,
            l.primer_contacto_en,
            l.registrado_en,
            l.actualizado_en
        FROM core.leads l
        LEFT JOIN core.empresas emp ON l.empresa_id = emp.empresa_id
        LEFT JOIN core.puntos_venta pv ON l.punto_venta_id = pv.punto_venta_id
        LEFT JOIN core.motocicletas m ON l.sku_motocicleta = m.sku
        LEFT JOIN LATERAL (
            SELECT
                ei.extraccion_id,
                ei.pago_inicial,
                ei.metodo_pago,
                ei.intencion_declarada,
                ei.objecion_principal,
                ei.solicita_cotizacion,
                ei.solicita_cita,
                ei.modelo_extraccion,
                ei.version_extraccion
            FROM core.extracciones_ia ei
            WHERE ei.lead_id = l.lead_id
            ORDER BY ei.extraido_en DESC NULLS LAST
            LIMIT 1
        ) e ON TRUE
        LEFT JOIN core.puntajes_leads p ON l.lead_id = p.lead_id AND p.es_actual = TRUE
        LEFT JOIN core.asignaciones a ON l.lead_id = a.lead_id AND a.es_actual = TRUE
        LEFT JOIN core.asesores asr ON a.asesor_id = asr.asesor_id
"""


def valor_ia_para_ui(valor):
    """
    Representa un valor de extracción IA para UI.
    NULL permanece None (no se convierte en 'No' ni False).
    """
    if valor is None:
        return None
    if valor is True:
        return "Sí"
    if valor is False:
        return "No"
    return valor


def factores_score_desde_db(razones) -> list[str]:
    """
    Lee las razones persistidas en core.puntajes_leads.razones.
    No recalcula el score.
    """
    if razones is None:
        return []
    if isinstance(razones, str):
        try:
            razones = json.loads(razones)
        except json.JSONDecodeError:
            return [razones]
    if not isinstance(razones, dict):
        return [str(razones)]
    factores = razones.get("factores_clave")
    if isinstance(factores, list):
        return [str(item) for item in factores if item is not None]
    return []


def get_leads_bandeja(
    conn: psycopg.Connection,
    estado_gestion: str | list[str] | None = None,
    empresa_id: str | None = None,
    punto_venta_id: str | None = None,
    canal: str | None = None,
    sku: str | None = None,
    temperatura: str | None = None,
    asesor_id: str | None = None,
    asignacion: str | None = None,
    busqueda: str | None = None,
    lead_id: str | None = None,
    ordenar_por: str = "prioridad",
    solo_reales: bool = False,
) -> list[dict]:
    """
    Bandeja de leads: una fila por lead_id.

    Orden predeterminado:
        puntaje_prioridad DESC, puntaje_urgencia DESC, registrado_en ASC
    """
    where_clauses = []
    params: list = []

    sql_base = SQL_BANDEJA_SELECT

    if lead_id:
        where_clauses.append("l.lead_id = %s")
        params.append(lead_id)

    if busqueda and busqueda.strip():
        # Búsqueda acotada en la base; no obliga a cargar la bandeja completa.
        termino = f"%{busqueda.strip()}%"
        where_clauses.append(
            "(l.nombre_cliente ILIKE %s OR l.telefono ILIKE %s OR l.lead_id ILIKE %s)"
        )
        params.extend([termino, termino, termino])

    if solo_reales:
        where_clauses.append("l.lead_id LIKE %s")
        params.append("LD-%")

    if empresa_id:
        where_clauses.append("l.empresa_id = %s")
        params.append(empresa_id)

    if punto_venta_id:
        where_clauses.append("l.punto_venta_id = %s")
        params.append(punto_venta_id)

    if canal:
        where_clauses.append("LOWER(l.canal) = LOWER(%s)")
        params.append(canal)

    if sku:
        where_clauses.append("(l.sku_motocicleta = %s OR l.texto_modelo_original = %s)")
        params.extend([sku, sku])

    if temperatura:
        where_clauses.append("LOWER(p.temperatura) = LOWER(%s)")
        params.append(temperatura)

    if asesor_id:
        where_clauses.append("a.asesor_id = %s")
        params.append(asesor_id)

    if asignacion:
        estado = asignacion.strip().upper()
        if estado in ("ASIGNADO", "ASIGNADOS"):
            where_clauses.append("a.asesor_id IS NOT NULL")
        elif estado in ("SIN ASIGNAR", "SIN_ASIGNAR"):
            where_clauses.append("a.asesor_id IS NULL")

    if estado_gestion:
        if isinstance(estado_gestion, str):
            estado_list = [estado_gestion]
        else:
            estado_list = list(estado_gestion)
        where_clauses.append(f"({SQL_ESTADO_GESTION_NORMALIZADO} = ANY(%s))")
        params.append(estado_list)

    if where_clauses:
        sql_base += " WHERE " + " AND ".join(where_clauses)

    if ordenar_por in ("fecha", "reciente"):
        sql_base += " ORDER BY l.registrado_en DESC NULLS LAST"
    elif ordenar_por == "urgencia":
        sql_base += (
            " ORDER BY p.puntaje_urgencia DESC NULLS LAST,"
            " p.puntaje_prioridad DESC NULLS LAST,"
            " l.registrado_en ASC NULLS LAST"
        )
    else:
        sql_base += (
            " ORDER BY p.puntaje_prioridad DESC NULLS LAST,"
            " p.puntaje_urgencia DESC NULLS LAST,"
            " l.registrado_en ASC NULLS LAST"
        )

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql_base, params)
        return cur.fetchall()


def get_leads(conn: psycopg.Connection) -> list[dict]:
    return get_leads_bandeja(conn, ordenar_por="prioridad")


def get_lead_by_id(conn: psycopg.Connection, lead_id: str) -> dict | None:
    rows = get_leads_bandeja(conn, lead_id=lead_id)
    return rows[0] if rows else None


def get_mensajes_lead(conn: psycopg.Connection, lead_id: str) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
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
            ORDER BY m.enviado_en ASC NULLS LAST, m.orden_mensaje ASC
            """,
            (lead_id,),
        )
        return cur.fetchall()


def get_eventos_lead(conn: psycopg.Connection, lead_id: str) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
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
            ORDER BY eg.fecha_evento ASC
            """,
            (lead_id,),
        )
        return cur.fetchall()


def get_extracciones_lead(conn: psycopg.Connection, lead_id: str) -> dict | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                extraccion_id,
                lead_id,
                conversacion_id,
                sku_motocicleta,
                pago_inicial,
                metodo_pago,
                intencion_declarada,
                objecion_principal,
                solicita_cotizacion,
                solicita_cita,
                modelo_extraccion,
                version_extraccion,
                extraido_en
            FROM core.extracciones_ia
            WHERE lead_id = %s
            ORDER BY extraido_en DESC NULLS LAST
            LIMIT 1
            """,
            (lead_id,),
        )
        return cur.fetchone()


def get_puntaje_lead(conn: psycopg.Connection, lead_id: str) -> dict | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                puntaje_id,
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
            FROM core.puntajes_leads
            WHERE lead_id = %s AND es_actual = TRUE
            LIMIT 1
            """,
            (lead_id,),
        )
        return cur.fetchone()


def get_valores_filtros(conn: psycopg.Connection) -> dict:
    """
    Valores distintos para filtros. Incluye IDs de empresa/PV/asesor
    para respetar la dimensión multiempresa.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT DISTINCT canal
            FROM core.leads
            WHERE canal IS NOT NULL
            ORDER BY canal
            """
        )
        canales = [r["canal"] for r in cur.fetchall()]

        cur.execute(
            """
            SELECT DISTINCT temperatura
            FROM core.puntajes_leads
            WHERE temperatura IS NOT NULL AND es_actual = TRUE
            ORDER BY temperatura
            """
        )
        temperaturas = [r["temperatura"] for r in cur.fetchall()]

        cur.execute(
            """
            SELECT empresa_id, nombre
            FROM core.empresas
            ORDER BY empresa_id
            """
        )
        empresas = cur.fetchall()

        cur.execute(
            """
            SELECT punto_venta_id, empresa_id, nombre
            FROM core.puntos_venta
            ORDER BY empresa_id, punto_venta_id
            """
        )
        puntos_venta = cur.fetchall()

        cur.execute(
            """
            SELECT asesor_id, empresa_id, punto_venta_id, nombre, activo
            FROM core.asesores
            ORDER BY empresa_id, nombre
            """
        )
        asesores = cur.fetchall()

        cur.execute(
            f"""
            SELECT DISTINCT {SQL_ESTADO_GESTION_NORMALIZADO.replace('l.estado_gestion', 'estado_gestion')} AS estado_norm
            FROM core.leads
            WHERE estado_gestion IS NOT NULL
            ORDER BY 1
            """
        )
        estados_normalizados = [r["estado_norm"] for r in cur.fetchall()]

        cur.execute(
            """
            SELECT DISTINCT estado_gestion
            FROM core.leads
            WHERE estado_gestion IS NOT NULL
            ORDER BY estado_gestion
            """
        )
        estados_originales = [r["estado_gestion"] for r in cur.fetchall()]

        cur.execute(
            """
            SELECT DISTINCT sku_motocicleta AS sku
            FROM core.leads
            WHERE sku_motocicleta IS NOT NULL
            ORDER BY 1
            """
        )
        skus = [r["sku"] for r in cur.fetchall()]

        cur.execute(
            """
            SELECT DISTINCT texto_modelo_original
            FROM core.leads
            WHERE texto_modelo_original IS NOT NULL
            ORDER BY 1
            """
        )
        modelos = [r["texto_modelo_original"] for r in cur.fetchall()]

    return {
        "canales": canales,
        "temperaturas": temperaturas,
        "empresas": empresas,
        "puntos_venta": puntos_venta,
        "asesores": asesores,
        "estados": estados_originales,
        "estados_normalizados": estados_normalizados,
        "skus": skus,
        "modelos": modelos,
    }


def get_catalogo_motocicletas(conn: psycopg.Connection) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT sku, marca, linea, cilindraje_cc, segmento, precio_lista
            FROM core.motocicletas
            WHERE activo = TRUE
            ORDER BY sku
            """
        )
        return cur.fetchall()
