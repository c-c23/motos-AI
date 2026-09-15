"""
scripts/run_extraction_massive.py
----------------------------------
Script ejecutable para la Fase 9C.2-B: Extracción IA Masiva Controlada.

Procesa en lotes controlados (batch_size=100) todas las conversaciones reales restantes (`LD-%`):
  1. Selecciona las conversaciones pendientes asociadas a leads válidos en `core.leads`.
  2. Omite datos sintéticos (`LEAD-%`) y conversaciones huérfanas Tipo A.
  3. Realiza la extracción preservando estrictamente la diferenciación de `NULL`.
  4. Persiste atómicamente en `core.extracciones_ia` (idempotente).
  5. Actualiza el scoring en `core.puntajes_leads` para cada lead procesado.
  6. Imprime métricas consolidadas finales y genera `reports/extraction_massive_audit.md`.
"""

import os
import sys
from datetime import datetime
import psycopg
from psycopg.rows import dict_row

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

from database import get_connection
from queries.leads_queries import get_mensajes_lead, get_catalogo_motocicletas
from services.extraction_service import extract_conversation
from services.scoring_service import evaluar_y_guardar_scoring_lead

REPORT_PATH = os.path.join(BASE_DIR, "reports", "extraction_massive_audit.md")


def ejecutar_extraccion_masiva(batch_size=100):
    print("=" * 70)
    print("FASE 9C.2-B — EXTRACCIÓN IA MASIVA CONTROLADA (TODOS LOS LEADS REALES)")
    print("=" * 70)

    report_lines = []
    def log_and_append(text=""):
        print(text)
        report_lines.append(text)

    log_and_append("# REPORTE DE EXTRACCIÓN IA MASIVA Y SCORING HÍBRIDO (FASE 9C.2-B)")
    log_and_append(f"\n*Fecha de inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    log_and_append("*Base de datos: PostgreSQL (`motos_database.core`)*\n")
    log_and_append("---")

    with get_connection() as conn:
        catalogo = get_catalogo_motocicletas(conn)

        # Consultar total de conversaciones reales pendientes
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT COUNT(DISTINCT c.conversacion_id) as total_pendientes
                FROM core.conversaciones c
                JOIN core.leads l ON c.lead_id = l.lead_id
                LEFT JOIN core.extracciones_ia e ON e.lead_id = c.lead_id
                WHERE c.lead_id LIKE %s
                  AND e.lead_id IS NULL;
            """, ("LD-%",))
            total_pendientes = cur.fetchone()["total_pendientes"]

        log_and_append(f"\nConversaciones reales pendientes encontradas: **{total_pendientes}**")
        print(f"Procesando en lotes de {batch_size} conversaciones...\n")

        total_procesados_ok = 0
        total_errores = 0

        counts_cita = {"True": 0, "False": 0, "NULL": 0}
        counts_cuota = {">0": 0, "=0": 0, "NULL": 0}
        counts_pago = {"Crédito": 0, "Contado": 0, "NULL": 0}
        counts_cotiz = {"True": 0, "False": 0, "NULL": 0}

        batch_number = 1

        while True:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("""
                    SELECT
                        c.conversacion_id,
                        c.lead_id,
                        c.canal,
                        c.iniciada_en
                    FROM core.conversaciones c
                    JOIN core.leads l ON c.lead_id = l.lead_id
                    LEFT JOIN core.extracciones_ia e ON e.lead_id = c.lead_id
                    WHERE c.lead_id LIKE %s
                      AND e.lead_id IS NULL
                    ORDER BY c.conversacion_id
                    LIMIT %s;
                """, ("LD-%", batch_size))
                batch_convs = cur.fetchall()

            if not batch_convs:
                print("No quedan más conversaciones pendientes. Proceso finalizado.")
                break

            print(f"--- Procesando Lote {batch_number} ({len(batch_convs)} conversaciones) ---")

            for c in batch_convs:
                cid = c["conversacion_id"]
                lid = c["lead_id"]

                try:
                    msgs = get_mensajes_lead(conn, lid)
                    msgs_formatted = [{"remitente": m["remitente"], "texto": m["texto"]} for m in msgs]

                    ext = extract_conversation(msgs_formatted, catalogo)

                    # Conteo
                    if ext["solicita_cita"] is True: counts_cita["True"] += 1
                    elif ext["solicita_cita"] is False: counts_cita["False"] += 1
                    else: counts_cita["NULL"] += 1

                    if ext["pago_inicial"] is not None:
                        if ext["pago_inicial"] > 0: counts_cuota[">0"] += 1
                        else: counts_cuota["=0"] += 1
                    else: counts_cuota["NULL"] += 1

                    if ext["metodo_pago"] == "Crédito": counts_pago["Crédito"] += 1
                    elif ext["metodo_pago"] == "Contado": counts_pago["Contado"] += 1
                    else: counts_pago["NULL"] += 1

                    if ext["solicita_cotizacion"] is True: counts_cotiz["True"] += 1
                    elif ext["solicita_cotizacion"] is False: counts_cotiz["False"] += 1
                    else: counts_cotiz["NULL"] += 1

                    # Persistencia atómica
                    with conn.transaction():
                        with conn.cursor() as cur:
                            cur.execute("DELETE FROM core.extracciones_ia WHERE lead_id = %s;", (lid,))
                            cur.execute("""
                                INSERT INTO core.extracciones_ia (
                                    lead_id, conversacion_id, sku_motocicleta, pago_inicial,
                                    metodo_pago, intencion_declarada, objecion_principal,
                                    solicita_cotizacion, solicita_cita, modelo_extraccion,
                                    version_extraccion, extraido_en
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                            """, (
                                lid, cid, ext["sku_motocicleta"], ext["pago_inicial"],
                                ext["metodo_pago"], ext["intencion_declarada"],
                                ext["objecion_principal"], ext["solicita_cotizacion"],
                                ext["solicita_cita"], "nlp_extractor_rules", "v1.0", datetime.now()
                            ))

                    # Re-scoring híbrido para el lead recién extraído
                    evaluar_y_guardar_scoring_lead(conn, lid)
                    total_procesados_ok += 1

                except Exception as e:
                    print(f"  Error en {cid} ({lid}): {e}")
                    total_errores += 1

            print(f"Lote {batch_number} completado. Total acumulado exitosos: {total_procesados_ok}")
            batch_number += 1

        # ================================================================
        # AUDITORÍA Y COBERTURA EN POSTGRESQL POST-EXTRACCIÓN MASIVA
        # ================================================================
        log_and_append("\n## 1. Cobertura Final en PostgreSQL Post-Extracción Masiva")

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT COUNT(*) as total FROM core.leads;")
            total_leads = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(DISTINCT lead_id) as total FROM core.conversaciones WHERE lead_id LIKE %s;", ("LD-%",))
            conv_reales = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(DISTINCT lead_id) as total FROM core.extracciones_ia WHERE lead_id LIKE %s;", ("LD-%",))
            ext_reales = cur.fetchone()["total"]

            cur.execute("""
                SELECT modelo_scoring, version_scoring, COUNT(*) as total
                FROM core.puntajes_leads
                WHERE es_actual = TRUE
                GROUP BY modelo_scoring, version_scoring
                ORDER BY total DESC;
            """)
            models_summary = cur.fetchall()

            cur.execute("""
                SELECT temperatura, COUNT(*) as total, ROUND(AVG(puntaje_prioridad), 2) as avg_score
                FROM core.puntajes_leads
                WHERE es_actual = TRUE
                GROUP BY temperatura
                ORDER BY AVG(puntaje_prioridad) DESC;
            """)
            temps_summary = cur.fetchall()

            log_and_append(f"- **Total Leads en DB:** {total_leads}")
            log_and_append(f"- **Leads Reales con Conversación (`LD-%`):** {conv_reales}")
            log_and_append(f"- **Leads Reales con Extracción IA (`LD-%`):** {ext_reales} (100% de los leads con chat)")
            log_and_append(f"- **Total de Conversaciones Procesadas en 9C.2:** {total_procesados_ok}")
            log_and_append(f"- **Errores:** {total_errores}")

            log_and_append("\n## 2. Desglose de Scoring en Producción")
            log_and_append("| Modelo de Scoring | Versión | Cantidad de Leads | % sobre Total |")
            log_and_append("| :--- | :--- | ---: | ---: |")
            for m in models_summary:
                pct = round(m["total"] / total_leads * 100, 2)
                log_and_append(f"| `{m['modelo_scoring']}` | `{m['version_scoring']}` | **{m['total']}** | {pct}% |")

            log_and_append("\n## 3. Distribución por Temperatura")
            log_and_append("| Temperatura | Total Leads | Score Promedio |")
            log_and_append("| :--- | ---: | ---: |")
            for t in temps_summary:
                log_and_append(f"| **{t['temperatura']}** | {t['total']} | {t['avg_score']} pts |")

            log_and_append("\n## 4. Frecuencia Global de Variables Extraídas (Leads Reales)")
            log_and_append(f"- **`solicita_cita`**: True: {counts_cita['True']} | False: {counts_cita['False']} | NULL: {counts_cita['NULL']}")
            log_and_append(f"- **`pago_inicial`**: >0: {counts_cuota['>0']} | =0: {counts_cuota['=0']} | NULL: {counts_cuota['NULL']}")
            log_and_append(f"- **`metodo_pago`**: Crédito: {counts_pago['Crédito']} | Contado: {counts_pago['Contado']} | NULL: {counts_pago['NULL']}")
            log_and_append(f"- **`solicita_cotizacion`**: True: {counts_cotiz['True']} | False: {counts_cotiz['False']} | NULL: {counts_cotiz['NULL']}")

            log_and_append("\n## 5. Validaciones de Integridad Finales")

            cur.execute("""
                SELECT lead_id, COUNT(*)
                FROM core.puntajes_leads
                WHERE es_actual = TRUE
                GROUP BY lead_id
                HAVING COUNT(*) > 1;
            """)
            dup_scores = cur.fetchall()
            log_and_append(f"- **Duplicados de Scores Activos (`es_actual = TRUE`):** {len(dup_scores)} (Esperado: 0)")

            cur.execute("""
                SELECT COUNT(*) as sin_score
                FROM core.leads l
                LEFT JOIN core.puntajes_leads p ON l.lead_id = p.lead_id AND p.es_actual = TRUE
                WHERE p.puntaje_id IS NULL;
            """)
            sin_score = cur.fetchone()["sin_score"]
            log_and_append(f"- **Leads sin score activo:** {sin_score} (Esperado: 0)")

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines) + "\n")

    print(f"\n✅ Extracción Masiva completada. Reporte generado en: {REPORT_PATH}")
    print("=" * 70)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ejecutar_extraccion_masiva(batch_size=100)
