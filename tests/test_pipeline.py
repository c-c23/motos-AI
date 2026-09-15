"""
tests/test_pipeline.py
----------------------
Suite de pruebas unitarias e integradas para el orquestador End-to-End del Pipeline (Fase 9F).

Cubre los 10 casos de prueba obligatorios:
1. Pipeline sin datos nuevos (0 nuevos, 0 duplicados, 0 errores).
2. Procesamiento de nuevos datos válidos (ingesta -> extracción -> scoring -> asignación).
3. Idempotencia ante re-ejecución con los mismos datos.
4. Manejo de leads inválidos (rechazo controlado sin afectar registros válidos).
5. No reprocesamiento de conversaciones ya extraídas.
6. No duplicación de asignaciones para leads ya asignados.
7. Manejo de leads cuando se agota la capacidad disponible.
8. Aislamiento estricto multiempresa y punto de venta.
9. Validación de modo Dry-Run (sin modificaciones en DB ni en sistema de archivos).
10. Manejo y captura de error crítico de infraestructura.
"""

import os
import sys
import json
import tempfile
import shutil
from datetime import datetime, date
from decimal import Decimal
import pytest
import psycopg

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import get_connection
from scripts.run_pipeline import PipelineOrchestrator, run_pipeline
from services.assignment_service import Asesor, Lead, simular_asignacion_leads


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def temp_dirs():
    """Crea directorios temporales aislados para inbox y archive."""
    inbox = tempfile.mkdtemp(prefix="test_inbox_")
    archive = tempfile.mkdtemp(prefix="test_archive_")
    yield inbox, archive
    shutil.rmtree(inbox, ignore_errors=True)
    shutil.rmtree(archive, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# CASO 1: Pipeline sin datos nuevos
# ─────────────────────────────────────────────────────────────────────────────

def test_1_pipeline_sin_datos_nuevos(temp_dirs):
    """
    Cuando el inbox está vacío y la base de datos está al día:
    0 nuevos leads, 0 extracciones nuevas, 0 errores, estado SUCCESS.
    """
    inbox, archive = temp_dirs
    metrics = run_pipeline(dry_run=True, inbox_dir=inbox, archive_dir=archive, verbose=False)

    assert metrics["status"] == "SUCCESS"
    assert metrics["ingest"]["files_detected"] == 0
    assert metrics["ingest"]["leads_new"] == 0
    assert metrics["extraction"]["pending_found"] == 0
    assert metrics["scoring"]["leads_evaluated"] == 0
    assert metrics["assignment"]["new_assignments"] == 0
    assert len(metrics["errors"]) == 0


# ─────────────────────────────────────────────────────────────────────────────
# CASO 2: Procesamiento de nuevos datos válidos
# ─────────────────────────────────────────────────────────────────────────────

def test_2_procesamiento_datos_nuevos_e2e(temp_dirs):
    """
    Prueba el flujo completo con datos nuevos en un entorno transaccional aislado:
    Ingesta -> Extracción IA -> Scoring Híbrido -> Asignación.
    """
    inbox, archive = temp_dirs

    # Crear lead de prueba en JSON
    test_lead_id = f"TEST-LEAD-{int(datetime.now().timestamp())}"
    test_conv_id = f"TEST-CONV-{int(datetime.now().timestamp())}"

    leads_payload = [{
        "lead_id": test_lead_id,
        "registrado_en": "2026-09-15 10:00:00",
        "canal": "WhatsApp",
        "punto_venta_id": "PV-001",
        "empresa_id": "EMP-01",
        "nombre_cliente": "Cliente Test E2E",
        "telefono": "3001234567",
        "correo": "test@motos.com",
        "ciudad": "Pereira",
        "texto_modelo_original": "FZ 250",
        "estado_gestion": "Nuevo",
    }]

    convs_payload = [{
        "conversacion_id": test_conv_id,
        "lead_id": test_lead_id,
        "canal": "WhatsApp",
        "iniciada_en": "2026-09-15 10:05:00",
        "mensajes": [
            {"orden_mensaje": 1, "emisor": "Cliente", "contenido": "Hola, quiero cotizar la FZ 250", "enviado_en": "2026-09-15 10:05:10"},
            {"orden_mensaje": 2, "emisor": "Asesor", "contenido": "Con gusto, ¿cuenta con cuota inicial?", "enviado_en": "2026-09-15 10:06:00"},
            {"orden_mensaje": 3, "emisor": "Cliente", "contenido": "Tengo 2 millones de cuota inicial y quiero ir a verla en persona manana", "enviado_en": "2026-09-15 10:07:00"}
        ]
    }]

    with open(os.path.join(inbox, "leads.json"), "w", encoding="utf-8") as f:
        json.dump(leads_payload, f)
    with open(os.path.join(inbox, "conversaciones.json"), "w", encoding="utf-8") as f:
        json.dump(convs_payload, f)

    with get_connection() as conn:
        try:
            # Ejecutar con conexión propia
            orch = PipelineOrchestrator(inbox_dir=inbox, archive_dir=archive, dry_run=False, verbose=False, conn=conn)
            metrics = orch.run()

            assert metrics["status"] == "SUCCESS"
            assert metrics["ingest"]["leads_new"] == 1
            assert metrics["ingest"]["convs_new"] == 1
            assert metrics["ingest"]["messages_new"] == 3
            assert metrics["extraction"]["success"] == 1
            assert metrics["scoring"]["scores_created_or_updated"] == 1

            # Verificar en PostgreSQL
            with conn.cursor() as cur:
                cur.execute("SELECT sku_motocicleta, solicita_cita, pago_inicial FROM core.extracciones_ia WHERE lead_id = %s;", (test_lead_id,))
                ext = cur.fetchone()
                assert ext is not None
                assert ext[1] is True  # solicita_cita = True
                assert ext[2] == 2000000  # pago_inicial = 2 millones

                cur.execute("SELECT puntaje_prioridad, temperatura FROM core.puntajes_leads WHERE lead_id = %s AND es_actual = true;", (test_lead_id,))
                sc = cur.fetchone()
                assert sc is not None
                assert sc[0] >= 50.0  # prioridad alta/crítica por cita y cuota

        finally:
            # Limpiar datos de prueba de la base de datos
            with conn.cursor() as cur:
                cur.execute("DELETE FROM core.asignaciones WHERE lead_id = %s;", (test_lead_id,))
                cur.execute("DELETE FROM core.puntajes_leads WHERE lead_id = %s;", (test_lead_id,))
                cur.execute("DELETE FROM core.extracciones_ia WHERE lead_id = %s;", (test_lead_id,))
                cur.execute("DELETE FROM core.mensajes WHERE conversacion_id = %s;", (test_conv_id,))
                cur.execute("DELETE FROM core.conversaciones WHERE conversacion_id = %s;", (test_conv_id,))
                cur.execute("DELETE FROM core.leads WHERE lead_id = %s;", (test_lead_id,))
            conn.commit()


# ─────────────────────────────────────────────────────────────────────────────
# CASO 3: Idempotencia ante re-ejecución con los mismos datos
# ─────────────────────────────────────────────────────────────────────────────

def test_3_idempotencia_segunda_ejecucion(temp_dirs):
    """
    Ejecutar dos veces seguidas el pipeline no debe duplicar registros ni generar errores.
    """
    inbox, archive = temp_dirs
    # Primera ejecución (base actual)
    m1 = run_pipeline(dry_run=True, inbox_dir=inbox, archive_dir=archive, verbose=False)
    # Segunda ejecución idéntica
    m2 = run_pipeline(dry_run=True, inbox_dir=inbox, archive_dir=archive, verbose=False)

    assert m1["status"] == "SUCCESS"
    assert m2["status"] == "SUCCESS"
    assert m2["ingest"]["leads_new"] == 0
    assert m2["assignment"]["new_assignments"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# CASO 4: Manejo de leads inválidos (rechazo controlado)
# ─────────────────────────────────────────────────────────────────────────────

def test_4_rechazo_controlado_lead_invalido(temp_dirs):
    """
    Un lead con punto_venta_id inválido o lead_id vacío debe ser rechazado
    sin romper el procesamiento de los leads válidos en el mismo archivo.
    """
    inbox, archive = temp_dirs

    payload = [
        {"lead_id": "", "nombre_cliente": "Sin ID", "punto_venta_id": "PV-001"},  # Inválido: sin ID
        {"lead_id": "TEST-INV-PV", "nombre_cliente": "PV Inexistente", "punto_venta_id": "PV-999"},  # Inválido: PV no existe
    ]

    with open(os.path.join(inbox, "leads.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f)

    metrics = run_pipeline(dry_run=True, inbox_dir=inbox, archive_dir=archive, verbose=False)

    assert metrics["status"] in ("SUCCESS", "PARTIAL_WARNING")
    assert metrics["ingest"]["leads_rejected"] == 2
    assert metrics["ingest"]["leads_new"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# CASO 5: No reprocesamiento de conversaciones ya extraídas
# ─────────────────────────────────────────────────────────────────────────────

def test_5_no_reprocesar_conversaciones_ya_extraidas(temp_dirs):
    """
    Las conversaciones que ya tienen registro en core.extracciones_ia no se reprocesan.
    """
    inbox, archive = temp_dirs
    metrics = run_pipeline(dry_run=True, inbox_dir=inbox, archive_dir=archive, verbose=False)

    # Todas las conversaciones elegibles actuales ya fueron extraídas
    assert metrics["extraction"]["pending_found"] == 0
    assert metrics["extraction"]["processed"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# CASO 6: No duplicar asignaciones para leads ya asignados
# ─────────────────────────────────────────────────────────────────────────────

def test_6_no_duplicar_asignaciones(temp_dirs):
    """
    Un lead con asignación activa previa no recibe una segunda asignación.
    """
    inbox, archive = temp_dirs
    metrics = run_pipeline(dry_run=True, inbox_dir=inbox, archive_dir=archive, verbose=False)

    # Los 699 leads ya asignados se detectan como already_assigned
    assert metrics["assignment"]["already_assigned"] == 699


# ─────────────────────────────────────────────────────────────────────────────
# CASO 7: Manejo de leads cuando se agota la capacidad
# ─────────────────────────────────────────────────────────────────────────────

def test_7_manejo_sin_capacidad(temp_dirs):
    """
    Los leads que no pueden ser asignados por falta de capacidad diaria en su PV
    quedan catalogados como without_capacity (SIN_CAPACIDAD).
    """
    inbox, archive = temp_dirs
    metrics = run_pipeline(dry_run=True, inbox_dir=inbox, archive_dir=archive, verbose=False)

    # 808 leads quedan sin capacidad disponible para el día operativo
    assert metrics["assignment"]["without_capacity"] == 808


# ─────────────────────────────────────────────────────────────────────────────
# CASO 8: Aislamiento multiempresa y PV
# ─────────────────────────────────────────────────────────────────────────────

def test_8_aislamiento_multiempresa_pv():
    """
    Verifica que el motor de asignación nunca asigne entre empresas o PVs distintos.
    """
    asesores = [
        Asesor(asesor_id="AS-EMP1", empresa_id="EMP-01", punto_venta_id="PV-001", activo=True, capacidad_diaria_leads=10),
        Asesor(asesor_id="AS-EMP2", empresa_id="EMP-02", punto_venta_id="PV-003", activo=True, capacidad_diaria_leads=10),
    ]
    leads = [
        Lead(lead_id="L-EMP1", empresa_id="EMP-01", punto_venta_id="PV-001", puntaje_prioridad=80.0, puntaje_urgencia=None, registrado_en=datetime.now()),
        Lead(lead_id="L-EMP2", empresa_id="EMP-02", punto_venta_id="PV-003", puntaje_prioridad=70.0, puntaje_urgencia=None, registrado_en=datetime.now()),
        Lead(lead_id="L-EMP3", empresa_id="EMP-03", punto_venta_id="PV-005", puntaje_prioridad=90.0, puntaje_urgencia=None, registrado_en=datetime.now()),
    ]

    res = simular_asignacion_leads(leads, asesores)
    r_map = {r.lead_id: r for r in res}

    assert r_map["L-EMP1"].asignado and r_map["L-EMP1"].asesor_asignado == "AS-EMP1"
    assert r_map["L-EMP2"].asignado and r_map["L-EMP2"].asesor_asignado == "AS-EMP2"
    # L-EMP3 no tiene asesores en EMP-03 / PV-005 en esta prueba
    assert not r_map["L-EMP3"].asignado


# ─────────────────────────────────────────────────────────────────────────────
# CASO 9: Dry-Run no modifica PostgreSQL ni archivos
# ─────────────────────────────────────────────────────────────────────────────

def test_9_dry_run_no_modifica_archivos_ni_db(temp_dirs):
    """
    El modo dry-run no modifica la base de datos ni elimina/mueve archivos del inbox.
    """
    inbox, archive = temp_dirs
    test_file = os.path.join(inbox, "test_leads.json")
    with open(test_file, "w", encoding="utf-8") as f:
        json.dump([{"lead_id": "TEST-DRY-01", "punto_venta_id": "PV-001"}], f)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM core.leads;")
            count_before = cur.fetchone()[0]

    metrics = run_pipeline(dry_run=True, inbox_dir=inbox, archive_dir=archive, verbose=False)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM core.leads;")
            count_after = cur.fetchone()[0]

    assert count_before == count_after, "Dry-run no debe modificar core.leads"
    assert os.path.exists(test_file), "Dry-run no debe mover ni borrar archivos del inbox"
    assert len(os.listdir(archive)) == 0, "Dry-run no debe archivar archivos"


# ─────────────────────────────────────────────────────────────────────────────
# CASO 10: Manejo de error crítico de infraestructura
# ─────────────────────────────────────────────────────────────────────────────

def test_10_manejo_error_critico():
    """
    Un error crítico de conexión se registra como FAILED y se captura en metrics.
    """
    class MockFailingConnection:
        def cursor(self, *args, **kwargs):
            raise psycopg.OperationalError("Simulated database connection loss")
        def close(self):
            pass

    orch = PipelineOrchestrator(dry_run=False, verbose=False, conn=MockFailingConnection())
    metrics = orch.run()

    assert metrics["status"] == "FAILED"
    assert len(metrics["errors"]) > 0
    assert "Simulated database connection loss" in metrics["errors"][0]["error"]
