from database import get_connection
from psycopg.rows import dict_row

with get_connection() as conn:
    with conn.cursor(row_factory=dict_row) as cur:
        print("--- by empresa ---")
        cur.execute(
            """
            SELECT l.empresa_id, emp.nombre, COUNT(*) n
            FROM core.leads l
            JOIN core.empresas emp ON emp.empresa_id = l.empresa_id
            GROUP BY 1, 2 ORDER BY 1
            """
        )
        for r in cur.fetchall():
            print(dict(r))

        print("--- with extraction ---")
        cur.execute(
            """
            SELECT COUNT(DISTINCT e.lead_id) n FROM core.extracciones_ia e
            """
        )
        print(dict(cur.fetchone()))

        print("--- extraction null cita ---")
        cur.execute(
            """
            SELECT e.lead_id, e.solicita_cita, e.solicita_cotizacion, e.pago_inicial, e.metodo_pago
            FROM core.extracciones_ia e
            WHERE e.solicita_cita IS NULL
            LIMIT 3
            """
        )
        for r in cur.fetchall():
            print(dict(r))

        print("--- no extraction ---")
        cur.execute(
            """
            SELECT l.lead_id
            FROM core.leads l
            LEFT JOIN core.extracciones_ia e ON e.lead_id = l.lead_id
            WHERE e.extraccion_id IS NULL AND l.lead_id LIKE 'LD-%'
            LIMIT 3
            """
        )
        for r in cur.fetchall():
            print(dict(r))

        print("--- with conversation ---")
        cur.execute(
            """
            SELECT c.lead_id, COUNT(m.mensaje_id) msgs
            FROM core.conversaciones c
            JOIN core.mensajes m ON m.conversacion_id = c.conversacion_id
            WHERE c.lead_id LIKE 'LD-%'
            GROUP BY 1
            HAVING COUNT(m.mensaje_id) > 2
            LIMIT 3
            """
        )
        for r in cur.fetchall():
            print(dict(r))

        print("--- synthetic leads ---")
        cur.execute("SELECT lead_id, campana FROM core.leads WHERE lead_id LIKE 'LEAD-%' ORDER BY 1")
        for r in cur.fetchall():
            print(dict(r))

        print("--- kpis current get_kpis view ---")
        cur.execute(
            """
            SELECT
                COUNT(*) AS total_leads,
                COUNT(asesor_id) AS leads_asignados,
                COUNT(*) FILTER (WHERE asesor_id IS NULL) AS leads_sin_asignar,
                COUNT(*) FILTER (WHERE temperatura IN ('Caliente', 'Alto', 'Crítico')) AS leads_calientes,
                COUNT(*) FILTER (WHERE temperatura IN ('Tibio', 'Medio')) AS leads_tibios,
                COUNT(*) FILTER (WHERE temperatura IN ('Frio', 'Bajo') OR temperatura IS NULL) AS leads_frios,
                COUNT(*) FILTER (WHERE estado_gestion = 'Nuevo') AS leads_nuevos
            FROM core.vw_leads_gestion
            """
        )
        print(dict(cur.fetchone()))
