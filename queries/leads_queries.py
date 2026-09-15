"""
queries/leads_queries.py
------------------------
Consultas SQL relacionadas con leads para el CRM Motos AI Leads.
Proporciona la capa de datos para la Bandeja de Leads y la ficha de detalle.
Todas las funciones reciben una conexión activa (psycopg.Connection)
y devuelven listas de diccionarios o un solo diccionario.
"""

from __future__ import annotations
import psycopg
from psycopg.rows import dict_row

# Expresión SQL estandarizada para la normalización semántica de estado_gestion
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


def get_leads_bandeja(
    conn: psycopg.Connection,
    estado_gestion: str | list[str] | None = None,
    empresa_id: str | None = None,
    punto_venta_id: str | None = None,
    canal: str | None = None,
    sku: str | None = None,
    temperatura: str | None = None,
    ordenar_por: str = "prioridad",
    solo_reales: bool = False,
) -> list[dict]:
    """
    Capa de consulta optimizada para la Bandeja de Leads CRM.
    
    Retorna los datos transformados para Streamlit con estado_gestion normalizado,
    información comercial, vehículo, extracciones de IA, scoring V1 e información del asesor asignado.
    
    Garantiza estricta unicidad (máximo 1 fila por lead_id).
    
    Filtros opcionales:
    - estado_gestion: string o lista de strings (ej. 'Sin gestión', ['Contactado', 'En proceso'])
    - empresa_id: string (ej. 'EMP-01')
    - punto_venta_id: string (ej. 'PV-003')
    - canal: string (ej. 'WhatsApp')
    - sku: string (ej. 'SKU-001')
    - temperatura: string (ej. 'Crítico', 'Caliente')
    - ordenar_por: 'prioridad' (default), 'fecha'/'reciente', 'urgencia'
    - solo_reales: bool (si True, filtra solo IDs reales LD-%)
    """
    where_clauses = []
    params = []

    sql_base = f"""
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
            l.estado_gestion AS estado_gestion,
            l.estado_gestion AS estado_gestion_original,
            {SQL_ESTADO_GESTION_NORMALIZADO} AS estado_gestion_normalizado,
            p.probabilidad_comercial,
            p.puntaje_urgencia,
            p.puntaje_prioridad,
            p.temperatura,
            p.modelo_scoring,
            p.version_scoring,
            p.puntuado_en AS fecha_calculo_scoring,
            a.asesor_id,
            asr.nombre AS asesor,
            l.primer_contacto_en,
            l.registrado_en,
            l.actualizado_en
        FROM core.leads l
        LEFT JOIN core.empresas emp ON l.empresa_id = emp.empresa_id
        LEFT JOIN core.puntos_venta pv ON l.punto_venta_id = pv.punto_venta_id
        LEFT JOIN core.motocicletas m ON l.sku_motocicleta = m.sku
        LEFT JOIN core.extracciones_ia e ON l.lead_id = e.lead_id
        LEFT JOIN core.puntajes_leads p ON l.lead_id = p.lead_id AND p.es_actual = true
        LEFT JOIN core.asignaciones a ON l.lead_id = a.lead_id AND a.es_actual = true
        LEFT JOIN core.asesores asr ON a.asesor_id = asr.asesor_id
    """

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
        where_clauses.append("l.sku_motocicleta = %s")
        params.append(sku)

    if temperatura:
        where_clauses.append("LOWER(p.temperatura) = LOWER(%s)")
        params.append(temperatura)

    if estado_gestion:
        if isinstance(estado_gestion, str):
            estado_list = [estado_gestion]
        else:
            estado_list = estado_gestion

        where_clauses.append(f"({SQL_ESTADO_GESTION_NORMALIZADO} = ANY(%s))")
        params.append(estado_list)

    if where_clauses:
        sql_base += " WHERE " + " AND ".join(where_clauses)

    if ordenar_por in ("fecha", "reciente"):
        sql_base += " ORDER BY l.registrado_en DESC NULLS LAST"
    elif ordenar_por == "urgencia":
        sql_base += " ORDER BY p.puntaje_urgencia DESC NULLS LAST, l.registrado_en DESC"
    else:
        sql_base += " ORDER BY p.puntaje_prioridad DESC NULLS LAST, l.registrado_en DESC"

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql_base, params)
        return cur.fetchall()


def get_leads(conn: psycopg.Connection) -> list[dict]:
    """
    Lee todos los leads desde la capa de consulta con estado_gestion_normalizado,
    ordenados por prioridad desc.
    """
    return get_leads_bandeja(conn, ordenar_por="prioridad")


def get_lead_by_id(conn: psycopg.Connection, lead_id: str) -> dict | None:
    """
    Lee un lead completo con estado_gestion_normalizado por su lead_id.
    Devuelve None si no existe.
    """
    leads = get_leads_bandeja(conn)
    for lead in leads:
        if lead["lead_id"] == lead_id:
            return lead
    return None


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
    Devuelve listas de: canales, temperaturas, empresas, puntos_venta, asesores, estados (originales y normalizados).
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT canal FROM core.leads
            WHERE canal IS NOT NULL ORDER BY canal;
        """)
        canales = [r[0] for r in cur.fetchall()]

        cur.execute("""
            SELECT DISTINCT temperatura FROM core.puntajes_leads
            WHERE temperatura IS NOT NULL ORDER BY temperatura;
        """)
        temperaturas = [r[0] for r in cur.fetchall()]

        cur.execute("""
            SELECT DISTINCT nombre FROM core.empresas
            WHERE nombre IS NOT NULL ORDER BY nombre;
        """)
        empresas = [r[0] for r in cur.fetchall()]

        cur.execute("""
            SELECT DISTINCT nombre FROM core.puntos_venta
            WHERE nombre IS NOT NULL ORDER BY nombre;
        """)
        puntos_venta = [r[0] for r in cur.fetchall()]

        cur.execute("""
            SELECT DISTINCT nombre FROM core.asesores
            WHERE nombre IS NOT NULL ORDER BY nombre;
        """)
        asesores = [r[0] for r in cur.fetchall()]

        cur.execute("""
            SELECT DISTINCT estado_gestion FROM core.leads
            WHERE estado_gestion IS NOT NULL ORDER BY estado_gestion;
        """)
        estados_originales = [r[0] for r in cur.fetchall()]

        cur.execute(f"""
            SELECT DISTINCT {SQL_ESTADO_GESTION_NORMALIZADO.replace('l.estado_gestion', 'estado_gestion')} AS estado_norm
            FROM core.leads
            WHERE estado_gestion IS NOT NULL
            ORDER BY 1;
        """)
        estados_normalizados = [r[0] for r in cur.fetchall()]

    return {
        "canales": canales,
        "temperaturas": temperaturas,
        "empresas": empresas,
        "puntos_venta": puntos_venta,
        "asesores": asesores,
        "estados": estados_originales,
        "estados_normalizados": estados_normalizados,
    }


def get_catalogo_motocicletas(conn: psycopg.Connection) -> list[dict]:
    """
    Lee todas las motocicletas activas para el matching/extracción de modelos.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT sku, marca, linea, cilindraje_cc, segmento, precio_lista
            FROM core.motocicletas
            WHERE activo = TRUE
            ORDER BY sku;
        """)
        return cur.fetchall()
