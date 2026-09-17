#!/usr/bin/env python
"""
scripts/run_pipeline.py
-----------------------

Arquitectura de ejecución secuencial:
1. Ingesta y normalización de nuevos datos (leads, conversaciones, mensajes).
2. Extracción de variables comerciales no estructuradas mediante IA (preservación de NULLs).
3. Scoring híbrido determinista (Logistic Regression V1 + Fallback Rules V1).
4. Asignación automática multiempresa por carga relativa y capacidad diaria.
5. Generación de resumen estructurado y métricas auditables.

Soporta:
- Ejecución normal: python scripts/run_pipeline.py
- Modo Dry-Run:     python scripts/run_pipeline.py --dry-run
- Configuración de inbox/archivo vía argumentos o variables de entorno.
"""

from __future__ import annotations
import os
import sys
import json
import shutil
import argparse
import traceback
from datetime import datetime, date
from decimal import Decimal
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple, Any

import pandas as pd
import psycopg
from psycopg.rows import dict_row

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from database import get_connection
from queries.leads_queries import get_catalogo_motocicletas, get_mensajes_lead
from services.extraction_service import extract_conversation
from services.scoring_service import (
    evaluar_y_guardar_scoring_lead,
    evaluar_scoring_hibrido,
    calcular_horas_sin_contacto,
)
from services.assignment_service import (
    Asesor,
    Lead,
    ResultadoAsignacion,
    simular_asignacion_leads,
    cargas_finales_de_simulacion,
    persistir_asignaciones,
    RAZON_YA_ASIGNADO,
    RAZON_SIN_CAPACIDAD,
)

SYNTHETIC_LEADS_PREV = {"LEAD-001", "LEAD-002", "LEAD-003", "LEAD-004", "LEAD-005", "LEAD-006", "LEAD-007"}


# ─────────────────────────────────────────────────────────────────────────────
# Utilidades de Normalización y Validación de Ingesta
# ─────────────────────────────────────────────────────────────────────────────

def _parsear_fecha(val: Any) -> Optional[datetime]:
    """Parseo robusto de fechas mixtas (DD-MM-YYYY, YYYY-MM-DD, ISO)."""
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    if not s or s.upper() in ("NAN", "NONE", "NULL", "NAT"):
        return None
    try:
        dt = pd.to_datetime(s, format="mixed", dayfirst=True)
        return dt.to_pydatetime()
    except Exception:
        return None


def _normalizar_canal(c: Any) -> Optional[str]:
    """Normaliza variantes de casing en canales."""
    if c is None or pd.isna(c):
        return None
    s = str(c).strip().lower()
    if not s or s == "nan":
        return None
    if "whatsapp" in s:
        return "WhatsApp"
    elif "meta" in s or "facebook" in s or "instagram" in s:
        return "Meta Ads"
    elif "form" in s or "web" in s:
        return "Formulario Web"
    elif "telegram" in s:
        return "Telegram"
    return str(c).strip().title()


def _normalizar_estado_gestion(e: Any) -> str:
    """Normaliza estado_gestion a categorías estándar."""
    if e is None or pd.isna(e) or not str(e).strip():
        return "Sin gestión"
    s = str(e).strip().lower()
    if s in ("sin gestion", "sin gestión"):
        return "Sin gestión"
    elif s == "contactado":
        return "Contactado"
    elif s == "no contesta":
        return "No contesta"
    elif s in ("cotización enviada", "cotizacion enviada"):
        return "Cotización enviada"
    elif s == "en proceso":
        return "En proceso"
    elif s == "descartado":
        return "Descartado"
    elif s == "cerrado":
        return "Cerrado"
    elif s == "perdido":
        return "Perdido"
    elif s == "nuevo":
        return "Nuevo"
    return str(e).strip().capitalize()


def _normalizar_emisor(em: Any) -> str:
    """Normaliza emisor de mensajes."""
    if not em or pd.isna(em):
        return "Cliente"
    s = str(em).strip().lower()
    if s == "cliente":
        return "Cliente"
    elif s == "asesor":
        return "Asesor"
    elif s == "bot":
        return "Bot"
    return str(em).strip().capitalize()


def _resolver_sku(texto: Any, catalogo: List[Dict[str, Any]]) -> Optional[str]:
    """Resuelve el SKU de motocicleta por coincidencia en catálogo."""
    if texto is None or pd.isna(texto) or not str(texto).strip():
        return None
    t = str(texto).strip().lower()
    for m in catalogo:
        sku = m.get("sku", "")
        if sku and sku.lower() == t:
            return sku
    for m in catalogo:
        linea = (m.get("linea") or "").lower()
        if linea and linea in t:
            return m.get("sku")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Clase Principal del Pipeline
# ─────────────────────────────────────────────────────────────────────────────

class PipelineOrchestrator:
    """
    Orquestador integral del pipeline end-to-end.
    """

    def __init__(
        self,
        inbox_dir: str = "data/inbox",
        archive_dir: str = "data/processed",
        dry_run: bool = False,
        verbose: bool = True,
        conn = None,
    ):
        self.inbox_dir = os.path.abspath(inbox_dir)
        self.archive_dir = os.path.abspath(archive_dir)
        self.dry_run = dry_run
        self.verbose = verbose
        self._external_conn = conn

        os.makedirs(self.inbox_dir, exist_ok=True)
        os.makedirs(self.archive_dir, exist_ok=True)

        self.metrics: Dict[str, Any] = {
            "started_at": None,
            "finished_at": None,
            "duration_seconds": 0.0,
            "dry_run": dry_run,
            "status": "NOT_STARTED",
            "ingest": {
                "files_detected": 0,
                "leads_detected": 0,
                "leads_new": 0,
                "leads_duplicate": 0,
                "leads_rejected": 0,
                "convs_detected": 0,
                "convs_new": 0,
                "messages_new": 0,
                "archived_files": [],
            },
            "extraction": {
                "pending_found": 0,
                "processed": 0,
                "success": 0,
                "errors": 0,
            },
            "scoring": {
                "leads_evaluated": 0,
                "scores_created_or_updated": 0,
                "logistic_regression_count": 0,
                "rules_count": 0,
                "errors": 0,
            },
            "assignment": {
                "leads_evaluated": 0,
                "already_assigned": 0,
                "new_assignments": 0,
                "without_capacity": 0,
                "other_unassigned": 0,
                "errors": 0,
            },
            "errors": [],
        }

    def log(self, message: str):
        if self.verbose:
            print(message)

    def run(self) -> Dict[str, Any]:
        """Ejecuta todas las etapas del pipeline en orden estricto."""
        self.metrics["started_at"] = datetime.now()
        self.log("=" * 75)
        self.log("PIPELINE END-TO-END — MOTOS AI LEADS")
        self.log(f"Modo: {'DRY-RUN (Sin escrituras)' if self.dry_run else 'PRODUCCIÓN / REAL'}")
        self.log(f"Inicio: {self.metrics['started_at'].strftime('%Y-%m-%d %H:%M:%S')}")
        self.log("=" * 75)

        own_conn = False
        conn = self._external_conn

        try:
            if conn is None:
                conn = get_connection()
                own_conn = True

            # Control de concurrencia mediante Advisory Lock en modo real
            if not self.dry_run:
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_xact_lock(hashtext('motos_ai_leads_pipeline_lock'));")
                self.log("[LOCK] Advisory lock de pipeline adquirido.")

            # Cargar mapas maestros de FK y catálogo
            pv_map, empresa_map, catalogo = self._load_metadata(conn)

            # ETAPA 1: Ingesta de nuevos datos desde inbox
            self.log("\n[ETAPA 1/4] Ingesta y normalización de nuevos datos...")
            self._stage_ingest(conn, pv_map, empresa_map, catalogo)

            # ETAPA 2: Extracción IA para conversaciones pendientes
            self.log("\n[ETAPA 2/4] Extracción de información con IA...")
            self._stage_extraction(conn, catalogo)

            # ETAPA 3: Scoring Híbrido
            self.log("\n[ETAPA 3/4] Cálculo de scoring y priorización comercial...")
            self._stage_scoring(conn)

            # ETAPA 4: Asignación automática
            self.log("\n[ETAPA 4/4] Asignación automática multiempresa...")
            self._stage_assignment(conn)

            if not self.dry_run and own_conn:
                conn.commit()

            self.metrics["status"] = "SUCCESS" if not self.metrics["errors"] else "PARTIAL_WARNING"

        except Exception as ex:
            if conn and not self.dry_run and own_conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            err_trace = traceback.format_exc()
            self.log(f"\n[ERROR CRÍTICO] Fallo en ejecución del pipeline:\n{err_trace}")
            self.metrics["status"] = "FAILED"
            self.metrics["errors"].append({"stage": "CRITICAL_PIPELINE", "error": str(ex), "trace": err_trace})

        finally:
            self.metrics["finished_at"] = datetime.now()
            duration = (self.metrics["finished_at"] - self.metrics["started_at"]).total_seconds()
            self.metrics["duration_seconds"] = round(duration, 3)

            if own_conn and conn:
                try:
                    conn.close()
                except Exception:
                    pass

        self._print_and_save_summary()
        return self.metrics

    # ─────────────────────────────────────────────────────────────────────────
    # Métodos Auxiliares y Etapas
    # ─────────────────────────────────────────────────────────────────────────

    def _load_metadata(self, conn) -> Tuple[Dict[str, str], Dict[str, str], List[Dict[str, Any]]]:
        """Carga mapa punto_venta -> empresa oficial y catálogo de motocicletas."""
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT punto_venta_id, empresa_id, nombre, ciudad FROM core.puntos_venta;")
            pv_rows = cur.fetchall()
            # punto_venta_id -> empresa_id oficial
            pv_to_empresa = {r["punto_venta_id"]: r["empresa_id"] for r in pv_rows}

            cur.execute("SELECT empresa_id, nombre FROM core.empresas;")
            emp_rows = cur.fetchall()
            empresas = {r["empresa_id"]: r["nombre"] for r in emp_rows}

        catalogo = get_catalogo_motocicletas(conn)
        return pv_to_empresa, empresas, catalogo

    def _stage_ingest(self, conn, pv_to_empresa: Dict[str, str], empresas: Dict[str, str], catalogo: List[Dict[str, Any]]):
        """Procesa archivos en inbox (leads CSV/JSON y conversaciones JSON)."""
        files = [
            f for f in os.listdir(self.inbox_dir)
            if f.endswith(".csv") or f.endswith(".json")
        ]
        self.metrics["ingest"]["files_detected"] = len(files)
        self.log(f"  - Archivos detectados en inbox ({self.inbox_dir}): {len(files)}")

        if not files:
            self.log("  - Inbox vacío. No hay nuevos archivos para ingerir.")
            return

        with conn.cursor(row_factory=dict_row) as cur:
            # Obtener set de leads ya existentes en PostgreSQL para deduplicación
            cur.execute("SELECT lead_id FROM core.leads;")
            existing_lead_ids: Set[str] = {r["lead_id"] for r in cur.fetchall()}

            cur.execute("SELECT conversacion_id FROM core.conversaciones;")
            existing_conv_ids: Set[str] = {r["conversacion_id"] for r in cur.fetchall()}

        leads_to_insert = []
        convs_to_insert = []
        msgs_to_insert = []
        archived_files = []
        leads_files = [f for f in files if f.endswith(".csv") or ("lead" in f.lower() and f.endswith(".json"))]
        convs_files = [f for f in files if "conv" in f.lower() and f.endswith(".json") and f not in leads_files]
        other_files = [f for f in files if f not in leads_files and f not in convs_files]
        ordered_files = sorted(leads_files) + sorted(convs_files) + sorted(other_files)

        for fname in ordered_files:
            fpath = os.path.join(self.inbox_dir, fname)
            self.log(f"  - Procesando archivo: {fname}")

            if fname.endswith(".csv") or ("lead" in fname.lower() and fname.endswith(".json")):
                # Ingesta de Leads
                try:
                    if fname.endswith(".csv"):
                        df = pd.read_csv(fpath, dtype=str)
                        records = df.to_dict(orient="records")
                    else:
                        with open(fpath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            records = data if isinstance(data, list) else data.get("leads", [])

                    self.metrics["ingest"]["leads_detected"] += len(records)

                    for row in records:
                        lid = str(row.get("lead_id") or row.get("id") or "").strip()
                        if not lid:
                            self.metrics["ingest"]["leads_rejected"] += 1
                            continue

                        if lid in existing_lead_ids:
                            self.metrics["ingest"]["leads_duplicate"] += 1
                            continue

                        pv_id = str(row.get("punto_venta_id") or "").strip()
                        if pv_id not in pv_to_empresa:
                            # PV inválido -> rechazado
                            self.metrics["ingest"]["leads_rejected"] += 1
                            continue

                        # Reconciliación: el PV determina la empresa oficial
                        emp_id = pv_to_empresa[pv_id]

                        reg_en = _parsear_fecha(row.get("registrado_en") or row.get("fecha_registro")) or datetime.now()
                        prim_cont = _parsear_fecha(row.get("primer_contacto_en") or row.get("fecha_primer_contacto"))
                        canal = _normalizar_canal(row.get("canal")) or "Formulario Web"
                        estado = _normalizar_estado_gestion(row.get("estado_gestion"))
                        nombre = str(row.get("nombre_cliente") or row.get("nombre") or "").strip() or "Cliente Sin Nombre"
                        tel = str(row.get("telefono") or "").strip() or None
                        correo = str(row.get("correo") or row.get("email") or "").strip() or None
                        ciudad = str(row.get("ciudad") or "").strip() or None
                        txt_modelo = str(row.get("texto_modelo_original") or row.get("modelo_interes_texto") or "").strip() or None
                        sku = _resolver_sku(row.get("sku_motocicleta") or txt_modelo, catalogo)
                        campana = str(row.get("campana") or row.get("campania") or "").strip() or None

                        leads_to_insert.append({
                            "lead_id": lid,
                            "registrado_en": reg_en,
                            "canal": canal,
                            "empresa_id": emp_id,
                            "punto_venta_id": pv_id,
                            "nombre_cliente": nombre,
                            "telefono": tel,
                            "correo": correo,
                            "ciudad": ciudad,
                            "texto_modelo_original": txt_modelo,
                            "sku_motocicleta": sku,
                            "estado_gestion": estado,
                            "primer_contacto_en": prim_cont,
                            "campana": campana,
                        })
                        existing_lead_ids.add(lid)
                        self.metrics["ingest"]["leads_new"] += 1

                    archived_files.append(fpath)

                except Exception as ex:
                    self.log(f"    [AVISO] Error leyendo archivo de leads {fname}: {ex}")
                    self.metrics["errors"].append({"stage": "INGEST_LEADS_FILE", "file": fname, "error": str(ex)})

            elif "conv" in fname.lower() and fname.endswith(".json"):
                # Ingesta de Conversaciones y Mensajes
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    conv_records = data if isinstance(data, list) else data.get("conversaciones", [])
                    self.metrics["ingest"]["convs_detected"] += len(conv_records)

                    for conv in conv_records:
                        cid = str(conv.get("conversacion_id") or conv.get("id") or "").strip()
                        lid = str(conv.get("lead_id") or "").strip()

                        if not cid or not lid:
                            continue

                        # Si el lead no existe ni está en el lote de leads nuevos, se omite (huérfano)
                        if lid not in existing_lead_ids:
                            continue

                        if cid in existing_conv_ids:
                            continue

                        canal = _normalizar_canal(conv.get("canal")) or "WhatsApp"
                        iniciada_en = _parsear_fecha(conv.get("iniciada_en") or conv.get("fecha_inicio")) or datetime.now()

                        convs_to_insert.append({
                            "conversacion_id": cid,
                            "lead_id": lid,
                            "canal": canal,
                            "iniciada_en": iniciada_en,
                        })
                        existing_conv_ids.add(cid)
                        self.metrics["ingest"]["convs_new"] += 1

                        # Mensajes
                        mensajes = conv.get("mensajes") or conv.get("messages") or []
                        for idx, m in enumerate(mensajes, start=1):
                            remitente = _normalizar_emisor(m.get("remitente") or m.get("emisor") or m.get("role"))
                            texto = str(m.get("texto") or m.get("contenido") or m.get("content") or "").strip()
                            enviado_en = _parsear_fecha(m.get("enviado_en") or m.get("timestamp")) or iniciada_en

                            msgs_to_insert.append({
                                "conversacion_id": cid,
                                "orden_mensaje": int(m.get("orden_mensaje") or idx),
                                "remitente": remitente,
                                "texto": texto,
                                "enviado_en": enviado_en,
                            })
                            self.metrics["ingest"]["messages_new"] += 1

                    archived_files.append(fpath)

                except Exception as ex:
                    self.log(f"    [AVISO] Error leyendo archivo de conversaciones {fname}: {ex}")
                    self.metrics["errors"].append({"stage": "INGEST_CONVS_FILE", "file": fname, "error": str(ex)})

        # Persistir en PostgreSQL si no es dry-run
        if not self.dry_run:
            with conn.cursor() as cur:
                # 1. Insertar Leads
                for l in leads_to_insert:
                    cur.execute("""
                        INSERT INTO core.leads (
                            lead_id, registrado_en, canal, empresa_id, punto_venta_id,
                            nombre_cliente, telefono, correo, ciudad, texto_modelo_original,
                            sku_motocicleta, estado_gestion, primer_contacto_en, campana
                        ) VALUES (
                            %(lead_id)s, %(registrado_en)s, %(canal)s, %(empresa_id)s, %(punto_venta_id)s,
                            %(nombre_cliente)s, %(telefono)s, %(correo)s, %(ciudad)s, %(texto_modelo_original)s,
                            %(sku_motocicleta)s, %(estado_gestion)s, %(primer_contacto_en)s, %(campana)s
                        ) ON CONFLICT (lead_id) DO NOTHING;
                    """, l)

                # 2. Insertar Conversaciones
                for c in convs_to_insert:
                    cur.execute("""
                        INSERT INTO core.conversaciones (
                            conversacion_id, lead_id, canal, iniciada_en
                        ) VALUES (
                            %(conversacion_id)s, %(lead_id)s, %(canal)s, %(iniciada_en)s
                        ) ON CONFLICT (conversacion_id) DO NOTHING;
                    """, c)

                # 3. Insertar Mensajes
                for m in msgs_to_insert:
                    cur.execute("""
                        INSERT INTO core.mensajes (
                            conversacion_id, orden_mensaje, remitente, texto, enviado_en
                        ) VALUES (
                            %(conversacion_id)s, %(orden_mensaje)s, %(remitente)s, %(texto)s, %(enviado_en)s
                        );
                    """, m)

            # Archivar archivos procesados de manera no destructiva
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            for src_path in archived_files:
                base_name = os.path.basename(src_path)
                dest_name = f"{timestamp_str}_{base_name}"
                dest_path = os.path.join(self.archive_dir, dest_name)
                try:
                    shutil.move(src_path, dest_path)
                    self.metrics["ingest"]["archived_files"].append(dest_name)
                except Exception as ex:
                    self.log(f"    [AVISO] No se pudo mover archivo procesado {base_name}: {ex}")

        self.log(f"  - Nuevos leads detectados e ingresados: {self.metrics['ingest']['leads_new']}")
        self.log(f"  - Nuevas conversaciones ingresadas:    {self.metrics['ingest']['convs_new']}")
        self.log(f"  - Nuevos mensajes ingresados:          {self.metrics['ingest']['messages_new']}")

    def _stage_extraction(self, conn, catalogo: List[Dict[str, Any]]):
        """Ejecuta extracción IA sobre conversaciones pendientes asociadas a core.leads."""
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
                WHERE e.lead_id IS NULL
                ORDER BY c.conversacion_id;
            """)
            pending_convs = cur.fetchall()

        self.metrics["extraction"]["pending_found"] = len(pending_convs)
        self.log(f"  - Conversaciones pendientes de extracción IA: {len(pending_convs)}")

        if not pending_convs:
            self.log("  - No hay extracciones IA pendientes.")
            return

        with conn.cursor(row_factory=dict_row) as cur:
            for c in pending_convs:
                cid = c["conversacion_id"]
                lid = c["lead_id"]
                try:
                    # Obtener mensajes ordenados
                    cur.execute("""
                        SELECT remitente as role, texto as content, enviado_en as timestamp
                        FROM core.mensajes
                        WHERE conversacion_id = %s
                        ORDER BY orden_mensaje ASC;
                    """, (cid,))
                    msgs = cur.fetchall()

                    extracted = extract_conversation(msgs, catalogo)

                    if not self.dry_run:
                        cur.execute("DELETE FROM core.extracciones_ia WHERE lead_id = %s;", (lid,))
                        cur.execute("""
                            INSERT INTO core.extracciones_ia (
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
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
                            );
                        """, (
                            lid,
                            cid,
                            extracted["sku_motocicleta"],
                            extracted["pago_inicial"],
                            extracted["metodo_pago"],
                            extracted["intencion_declarada"],
                            extracted["objecion_principal"],
                            extracted["solicita_cotizacion"],
                            extracted["solicita_cita"],
                            "rule_based",
                            "v1.0",
                        ))

                    self.metrics["extraction"]["success"] += 1
                except Exception as ex:
                    self.log(f"    [AVISO] Error en extracción para lead {lid}: {ex}")
                    self.metrics["extraction"]["errors"] += 1
                    self.metrics["errors"].append({"stage": "EXTRACTION", "lead_id": lid, "error": str(ex)})

                self.metrics["extraction"]["processed"] += 1

        self.log(f"  - Extracciones IA completadas con éxito: {self.metrics['extraction']['success']}")

    def _stage_scoring(self, conn):
        """Calcula scoring para leads sin score activo o con nuevas extracciones."""
        with conn.cursor(row_factory=dict_row) as cur:
            # Buscar leads en core.leads que no tengan score activo
            cur.execute("""
                SELECT l.lead_id
                FROM core.leads l
                LEFT JOIN core.puntajes_leads p ON p.lead_id = l.lead_id AND p.es_actual = true
                WHERE p.lead_id IS NULL
                ORDER BY l.lead_id;
            """)
            leads_pending = cur.fetchall()

        self.metrics["scoring"]["leads_evaluated"] = len(leads_pending)
        self.log(f"  - Leads pendientes de cálculo de scoring: {len(leads_pending)}")

        if not leads_pending:
            self.log("  - Todos los leads cuentan con scoring activo vigente.")
            return

        for r in leads_pending:
            lid = r["lead_id"]
            try:
                if self.dry_run:
                    # En dry-run evaluar scoring híbrido en memoria sin modificar la base de datos
                    with conn.cursor(row_factory=dict_row) as cur:
                        cur.execute("""
                            SELECT l.registrado_en, l.primer_contacto_en,
                                   e.solicita_cita, e.pago_inicial, e.metodo_pago
                            FROM core.leads l
                            LEFT JOIN core.extracciones_ia e ON e.lead_id = l.lead_id
                            WHERE l.lead_id = %s;
                        """, (lid,))
                        row_data = cur.fetchone()

                    horas, _ = calcular_horas_sin_contacto(
                        registrado_en=row_data["registrado_en"],
                        primer_contacto_en=row_data["primer_contacto_en"]
                    )
                    score_res = evaluar_scoring_hibrido(
                        horas=horas,
                        pidio_cita=row_data["solicita_cita"],
                        monto_cuota=row_data["pago_inicial"],
                        metodo_pago=row_data["metodo_pago"]
                    )
                    if "logistic_regression" in score_res.get("modelo_scoring", ""):
                        self.metrics["scoring"]["logistic_regression_count"] += 1
                    else:
                        self.metrics["scoring"]["rules_count"] += 1
                else:
                    # Persistir scoring real
                    evaluar_y_guardar_scoring_lead(conn, lid)
                    self.metrics["scoring"]["scores_created_or_updated"] += 1

            except Exception as ex:
                self.log(f"    [AVISO] Error en scoring para lead {lid}: {ex}")
                self.metrics["scoring"]["errors"] += 1
                self.metrics["errors"].append({"stage": "SCORING", "lead_id": lid, "error": str(ex)})

        if self.dry_run:
            self.metrics["scoring"]["scores_created_or_updated"] = (
                self.metrics["scoring"]["logistic_regression_count"] + self.metrics["scoring"]["rules_count"]
            )

        self.log(f"  - Scores calculados/actualizados: {self.metrics['scoring']['scores_created_or_updated']}")

    def _stage_assignment(self, conn):
        """Asigna leads elegibles a asesores respetando reglas multiempresa y capacidad diaria."""
        with conn.cursor(row_factory=dict_row) as cur:
            # 1. Asesores
            cur.execute("""
                SELECT asesor_id, empresa_id, punto_venta_id, activo, capacidad_diaria_leads
                FROM core.asesores
                ORDER BY asesor_id;
            """)
            raw_asesores = cur.fetchall()

            # 2. Leads con scores activos
            cur.execute("""
                SELECT l.lead_id, l.empresa_id, l.punto_venta_id, l.registrado_en,
                       p.puntaje_prioridad, p.puntaje_urgencia
                FROM core.leads l
                INNER JOIN core.puntajes_leads p
                    ON p.lead_id = l.lead_id AND p.es_actual = true
                ORDER BY l.lead_id;
            """)
            raw_leads = cur.fetchall()

            # 3. Asignaciones activas previas
            cur.execute("""
                SELECT lead_id FROM core.asignaciones WHERE es_actual = true;
            """)
            active_assigned_ids: Set[str] = {r["lead_id"] for r in cur.fetchall()}

            # 4. Cargas operativas del día de hoy
            today_date = date.today()
            cur.execute("""
                SELECT asesor_id, COUNT(*) as cnt
                FROM core.asignaciones
                WHERE DATE(asignado_en) = %s AND es_actual = true
                GROUP BY asesor_id;
            """, (today_date,))
            daily_loads = {r["asesor_id"]: r["cnt"] for r in cur.fetchall()}

        asesores = [
            Asesor(
                asesor_id=r["asesor_id"],
                empresa_id=r["empresa_id"],
                punto_venta_id=r["punto_venta_id"],
                activo=r["activo"],
                capacidad_diaria_leads=r["capacidad_diaria_leads"],
            )
            for r in raw_asesores
        ]

        leads = [
            Lead(
                lead_id=r["lead_id"],
                empresa_id=r["empresa_id"],
                punto_venta_id=r["punto_venta_id"],
                registrado_en=r["registrado_en"],
                puntaje_prioridad=float(r["puntaje_prioridad"]) if isinstance(r["puntaje_prioridad"], Decimal) else (r["puntaje_prioridad"] or 0.0),
                puntaje_urgencia=float(r["puntaje_urgencia"]) if r["puntaje_urgencia"] is not None and isinstance(r["puntaje_urgencia"], Decimal) else r["puntaje_urgencia"],
            )
            for r in raw_leads
        ]

        # Simulación y cálculo en memoria
        resultados = simular_asignacion_leads(
            leads=leads,
            asesores=asesores,
            cargas_iniciales=daily_loads,
            leads_ya_asignados=active_assigned_ids,
        )

        nuevas_asignaciones = [r for r in resultados if r.asignado]
        ya_asignados = [r for r in resultados if r.razon_sin_asignar == RAZON_YA_ASIGNADO]
        sin_capacidad = [r for r in resultados if r.razon_sin_asignar == RAZON_SIN_CAPACIDAD]
        otros_sin_asignar = [
            r for r in resultados
            if not r.asignado and r.razon_sin_asignar not in (RAZON_YA_ASIGNADO, RAZON_SIN_CAPACIDAD)
        ]

        self.metrics["assignment"]["leads_evaluated"] = len(leads)
        self.metrics["assignment"]["already_assigned"] = len(ya_asignados)
        self.metrics["assignment"]["new_assignments"] = len(nuevas_asignaciones)
        self.metrics["assignment"]["without_capacity"] = len(sin_capacidad)
        self.metrics["assignment"]["other_unassigned"] = len(otros_sin_asignar)

        if not self.dry_run:
            persistidos = persistir_asignaciones(conn, nuevas_asignaciones)
            self.metrics["assignment"]["new_assignments"] = persistidos

        self.log(f"  - Leads evaluados para asignación: {len(leads)}")
        self.log(f"  - Leads ya asignados previamente:  {len(ya_asignados)}")
        self.log(f"  - Nuevas asignaciones realizadas:  {self.metrics['assignment']['new_assignments']}")
        self.log(f"  - Leads sin capacidad disponible:  {len(sin_capacidad)}")

    def _print_and_save_summary(self):
        """Imprime resumen consolidado y genera archivo de ejecución."""
        m = self.metrics
        started_str = m["started_at"].strftime("%Y-%m-%d %H:%M:%S") if m["started_at"] else "N/A"
        finished_str = m["finished_at"].strftime("%Y-%m-%d %H:%M:%S") if m["finished_at"] else "N/A"

        summary_text = f"""
===========================================================================
RESUMEN DE EJECUCIÓN DEL PIPELINE ({m['status']})
Modo:                     {'DRY-RUN' if m['dry_run'] else 'REAL / PRODUCCIÓN'}
Inicio:                   {started_str}
Fin:                      {finished_str}
Duración:                 {m['duration_seconds']}s

[INGESTA]
- Archivos detectados:    {m['ingest']['files_detected']}
- Leads detectados:       {m['ingest']['leads_detected']}
- Leads nuevos:           {m['ingest']['leads_new']}
- Leads duplicados:       {m['ingest']['leads_duplicate']}
- Leads rechazados:       {m['ingest']['leads_rejected']}
- Conversaciones nuevas:  {m['ingest']['convs_new']}
- Mensajes nuevos:        {m['ingest']['messages_new']}

[EXTRACCIÓN IA]
- Pendientes detectadas:  {m['extraction']['pending_found']}
- Procesadas exitosas:    {m['extraction']['success']}
- Errores de extracción:  {m['extraction']['errors']}

[SCORING]
- Leads evaluados:        {m['scoring']['leads_evaluated']}
- Scores actualizados:    {m['scoring']['scores_created_or_updated']}
- Errores de scoring:     {m['scoring']['errors']}

[ASIGNACIÓN]
- Leads evaluados:        {m['assignment']['leads_evaluated']}
- Ya asignados:           {m['assignment']['already_assigned']}
- Nuevas asignaciones:    {m['assignment']['new_assignments']}
- Sin capacidad:          {m['assignment']['without_capacity']}
- Errores de asignación:  {m['assignment']['errors']}

ESTADO FINAL:             {m['status']}
===========================================================================
"""
        self.log(summary_text)

        # Guardar resumen en reports/pipeline_runs/
        if m["started_at"]:
            run_id = m["started_at"].strftime("%Y%m%d_%H%M%S")
            report_file = os.path.join(PROJECT_ROOT, "reports", "pipeline_runs", f"run_{run_id}.md")
            try:
                with open(report_file, "w", encoding="utf-8") as f:
                    f.write(f"# Reporte de Ejecución de Pipeline `{run_id}`\n\n```text\n{summary_text}\n```\n")
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# Punto de Entrada CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(description="Orquestador End-to-End del Pipeline (Motos AI Leads — Fase 9F)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Ejecuta en modo simulación de solo lectura (sin modificar PostgreSQL ni mover archivos).",
    )
    parser.add_argument(
        "--inbox-dir",
        type=str,
        default="data/inbox",
        help="Directorio de entrada para nuevos archivos de leads o conversaciones.",
    )
    parser.add_argument(
        "--archive-dir",
        type=str,
        default="data/processed",
        help="Directorio de archivo para datos procesados.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Silencia la salida en consola excepto errores.",
    )
    return parser.parse_args()


def run_pipeline(
    dry_run: bool = False,
    inbox_dir: str = "data/inbox",
    archive_dir: str = "data/processed",
    verbose: bool = True,
    conn = None,
) -> Dict[str, Any]:
    """Función programática para invocar el pipeline desde scripts o tests."""
    orchestrator = PipelineOrchestrator(
        inbox_dir=inbox_dir,
        archive_dir=archive_dir,
        dry_run=dry_run,
        verbose=verbose,
        conn=conn,
    )
    return orchestrator.run()


if __name__ == "__main__":
    args = parse_args()
    metrics = run_pipeline(
        dry_run=args.dry_run,
        inbox_dir=args.inbox_dir,
        archive_dir=args.archive_dir,
        verbose=not args.quiet,
    )
    if metrics["status"] == "FAILED":
        sys.exit(1)
    sys.exit(0)
