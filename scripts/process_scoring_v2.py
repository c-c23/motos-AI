"""
scripts/process_scoring_v2.py
-----------------------------
Proceso automático, modular, transaccional e idempotente para calcular y
guardar Scoring V2 en PostgreSQL (`core.puntajes_leads`) para los leads
que aún no cuentan con registro en versión v2.0.

Soporta:
  --dry-run      : Consulta estadísticas y muestra muestra de pendientes sin escribir en DB ni invocar IA.
  --limit N      : Procesa únicamente los primeros N leads pendientes.
  --delay S      : Pausa en segundos entre llamadas que involucran IA (precedencia: CLI -> SCORING_V2_DELAY -> 0.0s).
  (sin args)     : Procesa todos los leads pendientes de forma individual y segura.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import psycopg
from psycopg.rows import dict_row

from database import get_connection
from queries.leads_queries import get_mensajes_lead
from services.scoring_service import evaluar_y_guardar_scoring_v2_lead

logger = logging.getLogger("process_scoring_v2")


def configurar_logging(nivel: int = logging.INFO) -> None:
    """Configura el formato estándar de logging para el proceso."""
    logging.basicConfig(
        level=nivel,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )


def obtener_delay_configurado(delay_cli: Optional[float] = None) -> float:
    """
    Determina el delay en segundos con la siguiente precedencia:
      1. Argumento explícito --delay vía CLI (si se especifica)
      2. Variable de entorno SCORING_V2_DELAY
      3. 0.0 segundos por defecto (sin delay)
    """
    if delay_cli is not None:
        return max(0.0, float(delay_cli))

    env_val = os.getenv("SCORING_V2_DELAY")
    if env_val is not None and env_val.strip() != "":
        try:
            return max(0.0, float(env_val.strip()))
        except ValueError:
            logger.warning("Valor inválido en SCORING_V2_DELAY ('%s'), usando 0.0s", env_val)
            return 0.0

    return 0.0


def obtener_leads_pendientes_v2(
    conn: psycopg.Connection,
    limit: Optional[int] = None,
) -> List[str]:
    """
    Identifica leads en core.leads que no poseen ningún registro version_scoring = 'v2.0'.
    Ordenados por fecha de registro ascendente.
    """
    query = """
        SELECT l.lead_id
        FROM core.leads l
        LEFT JOIN core.puntajes_leads p
            ON p.lead_id = l.lead_id
            AND p.version_scoring = 'v2.0'
        WHERE p.lead_id IS NULL
        ORDER BY l.registrado_en ASC
    """
    if limit is not None and limit > 0:
        query += f" LIMIT {int(limit)}"

    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()
        return [r[0] for r in rows]


def obtener_estadisticas_dry_run(
    conn: psycopg.Connection,
    limit_sample: int = 5,
) -> Dict[str, Any]:
    """Obtiene métricas de conteo global y una muestra de leads pendientes para el modo dry-run."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM core.leads;")
        total_leads = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(DISTINCT lead_id)
            FROM core.puntajes_leads
            WHERE version_scoring = 'v2.0';
        """)
        leads_con_v2 = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*)
            FROM core.leads l
            LEFT JOIN core.puntajes_leads p
                ON p.lead_id = l.lead_id
                AND p.version_scoring = 'v2.0'
            WHERE p.lead_id IS NULL;
        """)
        leads_pendientes = cur.fetchone()[0]

    muestra = obtener_leads_pendientes_v2(conn, limit=limit_sample)

    return {
        "total_leads": total_leads,
        "leads_con_v2": leads_con_v2,
        "leads_pendientes": leads_pendientes,
        "muestra_pendientes": muestra,
    }


def ejecutar_dry_run(conn: Optional[psycopg.Connection] = None, limit_sample: int = 5) -> Dict[str, Any]:
    """Ejecuta la simulación dry-run imprimiendo el diagnóstico sin realizar escrituras."""
    def _run(c: psycopg.Connection) -> Dict[str, Any]:
        stats = obtener_estadisticas_dry_run(c, limit_sample=limit_sample)

        print("=" * 40)
        print("SCORING V2 - DRY RUN")
        print("=" * 40)
        print()
        print(f"Leads totales:       {stats['total_leads']}")
        print(f"Leads con V2:        {stats['leads_con_v2']}")
        print(f"Leads pendientes:    {stats['leads_pendientes']}")
        print()
        print("Primeros leads pendientes:")
        print()
        for idx, lid in enumerate(stats["muestra_pendientes"], 1):
            print(f"{idx}. {lid}")
        if not stats["muestra_pendientes"]:
            print("(Ningún lead pendiente)")
        print()
        print("No se realizaron modificaciones.")
        return stats

    if conn is not None:
        return _run(conn)
    else:
        with get_connection() as connection:
            return _run(connection)


def procesar_lead_individual(
    conn: psycopg.Connection,
    lead_id: str,
    mensajes: Optional[List[Dict[str, Any]]] = None,
    delay: float = 0.0,
) -> Dict[str, Any]:
    """
    Procesa un lead individual invocando la función centralizada evaluar_y_guardar_scoring_v2_lead.
    Aplica el delay configurable ÚNICAMENTE si el lead posee conversación/mensajes que requieran IA.
    """
    msgs = mensajes
    if msgs is None:
        try:
            msgs = get_mensajes_lead(conn, lead_id)
        except Exception:
            msgs = []

    tuvo_conversacion = bool(msgs and len(msgs) > 0)

    res = evaluar_y_guardar_scoring_v2_lead(conn=conn, lead_id=lead_id, mensajes=msgs)

    razones = res.get("razones", {})
    if isinstance(razones, str):
        try:
            razones = json.loads(razones)
        except Exception:
            razones = {}
    elif not isinstance(razones, dict):
        razones = {}

    modelo_extraccion = razones.get("modelo_extraccion", "reglas")
    puntaje = res.get("puntaje_prioridad")
    temperatura = res.get("temperatura")
    modelo_scoring = res.get("modelo_scoring", "hybrid_gemini")
    version_scoring = res.get("version_scoring", "v2.0")

    if modelo_extraccion == "gemini":
        categoria_extraccion = "gemini_ok"
    elif tuvo_conversacion:
        categoria_extraccion = "fallback_error_gemini"
    else:
        categoria_extraccion = "fallback_sin_conversacion"

    # Aplicar delay únicamente si la llamada a Gemini fue exitosa
    if categoria_extraccion == "gemini_ok" and delay > 0:
        logger.info("Aplicando delay de %.2fs tras llamada exitosa a Gemini para %s", delay, lead_id)
        time.sleep(delay)

    return {
        "lead_id": lead_id,
        "status": "OK",
        "puntaje_prioridad": float(puntaje) if puntaje is not None else None,
        "temperatura": temperatura,
        "modelo_scoring": modelo_scoring,
        "modelo_extraccion": modelo_extraccion,
        "categoria_extraccion": categoria_extraccion,
        "tuvo_conversacion": tuvo_conversacion,
        "version_scoring": version_scoring,
    }


def procesar_lote_v2(
    conn: Optional[psycopg.Connection] = None,
    limit: Optional[int] = None,
    delay: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Coordina el procesamiento por lote de leads pendientes de Scoring V2.
    Procesa uno a uno con aislamiento de fallos, control de ritmo (delay) y resumen final detallado.
    """
    delay_segundos = obtener_delay_configurado(delay)
    tiempo_inicio = time.time()
    logger.info("Inicio procesamiento V2 (delay configurado: %.2fs)", delay_segundos)

    def _ejecutar(c: psycopg.Connection) -> Dict[str, Any]:
        pendientes = obtener_leads_pendientes_v2(c, limit=limit)
        total_pendientes = len(pendientes)
        logger.info("Leads pendientes detectados: %d", total_pendientes)

        detalles: List[Dict[str, Any]] = []
        errores_detalle: List[Dict[str, Any]] = []

        procesados_ok = 0
        con_llamadas_gemini = 0
        fallback_sin_conversacion = 0
        fallback_error_gemini = 0
        total_errores = 0

        for lead_id in pendientes:
            logger.info("Procesando %s", lead_id)
            try:
                if c.closed:
                    c = get_connection()

                item_res = procesar_lead_individual(c, lead_id, delay=delay_segundos)
                detalles.append(item_res)
                procesados_ok += 1

                cat = item_res["categoria_extraccion"]
                if cat == "gemini_ok":
                    con_llamadas_gemini += 1
                elif cat == "fallback_sin_conversacion":
                    fallback_sin_conversacion += 1
                    logger.info("Sin conversación para %s (fallback reglas directo)", lead_id)
                elif cat == "fallback_error_gemini":
                    fallback_error_gemini += 1
                    logger.warning("Fallo en extracción Gemini para %s (fallback a reglas)", lead_id)

                logger.info("V2 guardado correctamente para %s", lead_id)

            except Exception as e:
                total_errores += 1
                err_info = {
                    "lead_id": lead_id,
                    "error": str(e),
                    "tipo_error": type(e).__name__,
                    "etapa": "scoring_v2_persistencia",
                }
                errores_detalle.append(err_info)
                detalles.append({
                    "lead_id": lead_id,
                    "status": "ERROR",
                    "error": str(e),
                })
                logger.error("Error procesando %s: %s", lead_id, e)

        duracion_total = time.time() - tiempo_inicio
        logger.info("Procesamiento finalizado en %.2fs", duracion_total)

        resumen = {
            "pendientes_detectados": total_pendientes,
            "procesados_correctamente": procesados_ok,
            "con_llamadas_gemini": con_llamadas_gemini,
            "fallback_sin_conversacion": fallback_sin_conversacion,
            "fallback_error_gemini": fallback_error_gemini,
            "fallback_reglas": fallback_sin_conversacion + fallback_error_gemini,
            "errores": total_errores,
            "delay_configurado": delay_segundos,
            "duracion_segundos": duracion_total,
            "detalles": detalles,
            "errores_detalle": errores_detalle,
        }

        # Imprimir resumen amigable en consola
        imprimir_resumen_lote(resumen)
        return resumen

    if conn is not None:
        return _ejecutar(conn)
    else:
        with get_connection() as connection:
            return _ejecutar(connection)


def imprimir_resumen_lote(resumen: Dict[str, Any]) -> None:
    """Imprime el resumen estructurado en stdout según las especificaciones."""
    print()
    print("=" * 50)
    print("RESUMEN SCORING V2")
    print("=" * 50)
    print(f"Pendientes detectados:       {resumen['pendientes_detectados']}")
    print(f"Procesados correctamente:    {resumen['procesados_correctamente']}")
    print(f"Errores:                     {resumen['errores']}")
    print()
    print("Extracción Semántica:")
    print(f"  Con llamadas Gemini:       {resumen.get('con_llamadas_gemini', 0)}")
    print(f"  Fallback sin conversación: {resumen.get('fallback_sin_conversacion', 0)}")
    print(f"  Fallback por error Gemini: {resumen.get('fallback_error_gemini', 0)}")
    print()
    print(f"Delay configurado:           {resumen.get('delay_configurado', 0.0):.1f} s")
    print(f"Duración total:              {resumen.get('duracion_segundos', 0.0):.2f} s")
    print()
    print("=" * 50)
    print("DETALLE")
    print("=" * 50)

    for item in resumen["detalles"]:
        lid = item.get("lead_id")
        if item.get("status") == "OK":
            mod_ext = item.get("modelo_extraccion", "reglas")
            cat = item.get("categoria_extraccion", "")
            if cat == "fallback_sin_conversacion":
                mod_desc = "reglas (sin conversación)"
            elif cat == "fallback_error_gemini":
                mod_desc = "reglas (error Gemini)"
            else:
                mod_desc = mod_ext

            pts = f"{item.get('puntaje_prioridad', 0.0):.2f}"
            temp = item.get("temperatura", "N/A")
            print(f"{lid} → OK → {mod_desc} → {pts} → {temp}")
        else:
            err = item.get("error", "Error desconocido")
            print(f"{lid} → ERROR → {err}")

    print("=" * 50)
    print("FINALIZADO")
    print("=" * 50)
    print()


def main(argv: Optional[List[str]] = None) -> int:
    """Punto de entrada CLI."""
    parser = argparse.ArgumentParser(
        description="Procesamiento por lote automatizado de Scoring V2."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulación: consulta pendientes sin llamar a Gemini ni escribir en PostgreSQL.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limita la cantidad de leads pendientes a procesar.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=None,
        help="Segundos de pausa entre llamadas a Gemini (por defecto 0.0 o variable SCORING_V2_DELAY).",
    )

    args = parser.parse_args(argv)
    configurar_logging()

    if args.dry_run:
        ejecutar_dry_run()
        return 0

    res = procesar_lote_v2(limit=args.limit, delay=args.delay)
    return 0 if res["errores"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
