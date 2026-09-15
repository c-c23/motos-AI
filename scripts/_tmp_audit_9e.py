from database import get_connection
from psycopg.rows import dict_row

with get_connection() as conn:
    with conn.cursor(row_factory=dict_row) as cur:
        queries = {
            "leads": "SELECT COUNT(*) AS n FROM core.leads",
            "scores": "SELECT COUNT(*) AS n FROM core.puntajes_leads WHERE es_actual = true",
            "asig": "SELECT COUNT(*) AS n FROM core.asignaciones",
            "asig_act": "SELECT COUNT(*) AS n FROM core.asignaciones WHERE es_actual = true",
            "asig_ld": "SELECT COUNT(*) AS n FROM core.asignaciones a WHERE a.es_actual AND a.lead_id LIKE 'LD-%'",
            "asig_lead": "SELECT COUNT(*) AS n FROM core.asignaciones WHERE es_actual AND lead_id LIKE 'LEAD-%'",
            "sin_asig": """
                SELECT COUNT(*) AS n
                FROM core.leads l
                LEFT JOIN core.asignaciones a ON l.lead_id = a.lead_id AND a.es_actual = true
                WHERE a.asignacion_id IS NULL
            """,
            "asesores": "SELECT COUNT(*) AS n FROM core.asesores",
            "ases_act": "SELECT COUNT(*) AS n FROM core.asesores WHERE activo = true",
            "ases_inact": "SELECT COUNT(*) AS n FROM core.asesores WHERE activo = false",
            "emp": "SELECT COUNT(*) AS n FROM core.empresas",
            "pv": "SELECT COUNT(*) AS n FROM core.puntos_venta",
            "vw": "SELECT COUNT(*) AS n FROM core.vw_leads_gestion",
            "ext_dups": """
                SELECT COUNT(*) AS n FROM (
                    SELECT lead_id FROM core.extracciones_ia GROUP BY lead_id HAVING COUNT(*) > 1
                ) t
            """,
            "bandeja_rows": """
                SELECT COUNT(*) AS n FROM (
                    SELECT l.lead_id
                    FROM core.leads l
                    LEFT JOIN core.extracciones_ia e ON l.lead_id = e.lead_id
                    LEFT JOIN core.puntajes_leads p ON l.lead_id = p.lead_id AND p.es_actual = true
                    LEFT JOIN core.asignaciones a ON l.lead_id = a.lead_id AND a.es_actual = true
                ) t
            """,
        }
        for k, q in queries.items():
            cur.execute(q)
            print(k, dict(cur.fetchone()))

        print("--- temperaturas ---")
        cur.execute(
            "SELECT temperatura, COUNT(*) n FROM core.puntajes_leads WHERE es_actual GROUP BY 1 ORDER BY 2 DESC"
        )
        for r in cur.fetchall():
            print(dict(r))

        print("--- estados ---")
        cur.execute("SELECT estado_gestion, COUNT(*) n FROM core.leads GROUP BY 1 ORDER BY 2 DESC")
        for r in cur.fetchall():
            print(dict(r))

        print("--- asignaciones cols ---")
        cur.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema='core' AND table_name='asignaciones'
            ORDER BY ordinal_position
            """
        )
        for r in cur.fetchall():
            print(dict(r))

        print("--- puntajes cols ---")
        cur.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema='core' AND table_name='puntajes_leads'
            ORDER BY ordinal_position
            """
        )
        for r in cur.fetchall():
            print(dict(r))

        print("--- extracciones cols ---")
        cur.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema='core' AND table_name='extracciones_ia'
            ORDER BY ordinal_position
            """
        )
        for r in cur.fetchall():
            print(dict(r))

        print("--- mensajes remitente ---")
        cur.execute("SELECT remitente, COUNT(*) n FROM core.mensajes GROUP BY 1")
        for r in cur.fetchall():
            print(dict(r))

        print("--- empresas ---")
        cur.execute("SELECT empresa_id, nombre FROM core.empresas ORDER BY 1")
        for r in cur.fetchall():
            print(dict(r))

        print("--- sample unassigned ---")
        cur.execute(
            """
            SELECT l.lead_id, l.estado_gestion, a.asesor_id
            FROM core.leads l
            LEFT JOIN core.asignaciones a ON l.lead_id = a.lead_id AND a.es_actual
            WHERE a.asignacion_id IS NULL
            LIMIT 3
            """
        )
        for r in cur.fetchall():
            print(dict(r))

        print("--- sample assigned ---")
        cur.execute(
            """
            SELECT l.lead_id, asr.nombre, a.asignado_en
            FROM core.leads l
            JOIN core.asignaciones a ON l.lead_id = a.lead_id AND a.es_actual
            JOIN core.asesores asr ON a.asesor_id = asr.asesor_id
            LIMIT 3
            """
        )
        for r in cur.fetchall():
            print(dict(r))

        print("--- sample razones ---")
        cur.execute(
            """
            SELECT lead_id, temperatura, puntaje_prioridad, razones
            FROM core.puntajes_leads
            WHERE es_actual
            LIMIT 2
            """
        )
        for r in cur.fetchall():
            print(r["lead_id"], r["temperatura"], r["puntaje_prioridad"], str(r["razones"])[:300])

        print("--- pendientes guess ---")
        cur.execute(
            """
            SELECT COUNT(*) n FROM core.leads
            WHERE LOWER(TRIM(estado_gestion)) IN ('nuevo', 'sin gestion', 'sin gestión')
            """
        )
        print(dict(cur.fetchone()))
        cur.execute(
            """
            SELECT COUNT(*) n FROM core.leads
            WHERE LOWER(TRIM(COALESCE(estado_gestion,''))) NOT IN ('descartado')
            """
        )
        print("not descartado", dict(cur.fetchone()))
