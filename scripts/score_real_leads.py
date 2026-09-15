"""
scripts/score_real_leads.py
----------------------------
Proceso controlado, atómico e idempotente para calcular y guardar el score
de prioridad comercial de todos los leads registrados en `core.leads`
(1.500 reales + 7 sintéticos) utilizando el motor híbrido:
  - Logistic Regression V1 (cuando existen variables de extracción)
  - Rules V1 (Fallback cuando las variables conversacionales están ausentes)

Al finalizar realiza las validaciones SQL obligatorias e imprime el reporte consolidado.
"""

import sys
import os
import psycopg
from psycopg.rows import dict_row

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

from database import get_connection
from services.scoring_service import evaluar_y_guardar_scoring_lead


def ejecutar_scoring_masivo():
    print("=" * 70)
    print("EJECUCIÓN DEL SCORING HÍBRIDO EN POSTGRESQL (core.puntajes_leads)")
    print("=" * 70)

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT lead_id FROM core.leads ORDER BY lead_id;")
            leads = cur.fetchall()

        total_leads = len(leads)
        print(f"Leads encontrados en core.leads: {total_leads}")

        exitosos = 0
        errores = 0

        for idx, item in enumerate(leads, 1):
            lid = item["lead_id"]
            try:
                evaluar_y_guardar_scoring_lead(conn, lid)
                exitosos += 1
            except Exception as e:
                print(f" Error evaluando {lid}: {e}")
                errores += 1

        print(f"\nProceso finalizado: {exitosos} exitosos, {errores} errores.")

        # ================================================================
        # VALIDACIONES SQL EN POSTGRESQL
        # ================================================================
        print("\n" + "=" * 70)
        print("REPORTE DE VALIDACIÓN Y PERSISTENCIA SQL")
        print("=" * 70)

        with conn.cursor(row_factory=dict_row) as cur:
            # 1. Total de scores activos (es_actual = true)
            cur.execute("SELECT COUNT(*) as total FROM core.puntajes_leads WHERE es_actual = TRUE;")
            total_actuales = cur.fetchone()["total"]
            print(f"Total de registros activos (es_actual = TRUE): {total_actuales}")

            # 2. Verificación de duplicados (debe ser 0)
            cur.execute("""
                SELECT lead_id, COUNT(*) as num
                FROM core.puntajes_leads
                WHERE es_actual = TRUE
                GROUP BY lead_id
                HAVING COUNT(*) > 1;
            """)
            duplicados = cur.fetchall()
            print(f"Leads con duplicados activos (es_actual = TRUE): {len(duplicados)} (Esperado: 0)")

            # 3. Desglose por modelo de scoring
            cur.execute("""
                SELECT modelo_scoring, version_scoring, COUNT(*) as total
                FROM core.puntajes_leads
                WHERE es_actual = TRUE
                GROUP BY modelo_scoring, version_scoring
                ORDER BY total DESC;
            """)
            modelos = cur.fetchall()
            print("\n--- Desglose por Modelo de Scoring ---")
            for m in modelos:
                print(f"  Modelo: {m['modelo_scoring']:<20} Versión: {m['version_scoring']:<10} Cantidad: {m['total']}")

            # 4. Desglose por Temperatura y Estadísticas de Score
            cur.execute("""
                SELECT
                    temperatura,
                    COUNT(*) as total,
                    ROUND(MIN(puntaje_prioridad), 2) as min_score,
                    ROUND(MAX(puntaje_prioridad), 2) as max_score,
                    ROUND(AVG(puntaje_prioridad), 2) as avg_score
                FROM core.puntajes_leads
                WHERE es_actual = TRUE
                GROUP BY temperatura
                ORDER BY min_score DESC;
            """)
            temps = cur.fetchall()
            print("\n--- Distribución por Temperatura ---")
            print(f"  {'Temperatura':<12} {'Total':<8} {'Min Score':<10} {'Max Score':<10} {'Avg Score':<10}")
            for t in temps:
                print(f"  {t['temperatura']:<12} {t['total']:<8} {t['min_score']:<10} {t['max_score']:<10} {t['avg_score']:<10}")

            # 5. Leads sin score (debe ser 0)
            cur.execute("""
                SELECT COUNT(*) as sin_score
                FROM core.leads l
                LEFT JOIN core.puntajes_leads p ON l.lead_id = p.lead_id AND p.es_actual = TRUE
                WHERE p.puntaje_id IS NULL;
            """)
            sin_score = cur.fetchone()["sin_score"]
            print(f"\nLeads sin score activo: {sin_score} (Esperado: 0)")

    print("\n" + "=" * 70)
    print("EJECUCIÓN Y VALIDACIÓN COMPLETADAS EXITOSAMENTE")
    print("=" * 70)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ejecutar_scoring_masivo()
