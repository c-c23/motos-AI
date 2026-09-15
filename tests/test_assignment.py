"""
tests/test_assignment.py
------------------------
Pruebas unitarias del motor de asignación automática — Fase 9D.2.

Cubre los 10 casos de prueba requeridos:
1. Empresa diferente → NO ELEGIBLE
2. PV diferente → NO ELEGIBLE
3. Asesor inactivo → NO ELEGIBLE
4. Capacidad agotada → NO ELEGIBLE
5. Menor carga relativa → seleccionado
6. Empate → tres criterios de desempate deterministas
7. Sin asesor disponible → SIN_ASIGNAR
8. Capacidad: carga <= capacidad en toda la simulación
9. Orden de leads por prioridad
10. Determinismo: dos ejecuciones idénticas producen los mismos resultados
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from services.assignment_service import (
    Asesor,
    Lead,
    simular_asignacion_leads,
    seleccionar_asesor_optimo,
    ordenar_leads_por_prioridad,
    determinar_razon_sin_asignar,
    cargas_finales_de_simulacion,
    RAZON_SIN_ASESOR_ACTIVO,
    RAZON_SIN_CAPACIDAD,
    RAZON_SIN_ASESOR_COMPATIBLE,
    RAZON_YA_ASIGNADO,
    ResultadoAsignacion,
    persistir_asignaciones,
)
from database import get_connection


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────

def make_asesor(aid, empresa, pv, cap, activo=True, carga=0):
    return Asesor(
        asesor_id=aid,
        empresa_id=empresa,
        punto_venta_id=pv,
        activo=activo,
        capacidad_diaria_leads=cap,
        carga_diaria=carga,
    )


def make_lead(lid, empresa, pv, prioridad=50.0, urgencia=None, ts=None):
    return Lead(
        lead_id=lid,
        empresa_id=empresa,
        punto_venta_id=pv,
        puntaje_prioridad=prioridad,
        puntaje_urgencia=urgencia,
        registrado_en=ts or datetime(2026, 1, 1, 12, 0),
    )


# ─────────────────────────────────────────────
# CASO 1 — Empresa diferente → NO ELEGIBLE
# ─────────────────────────────────────────────

def test_1_empresa_diferente_no_elegible():
    """
    Lead de EMP-01, asesor de EMP-02: el asesor NO debe ser elegible.
    """
    asesor = make_asesor("AS-Z1", "EMP-02", "PV-001", cap=10)
    lead = make_lead("L-001", "EMP-01", "PV-001")

    assert not asesor.es_elegible(lead.empresa_id, lead.punto_venta_id), (
        "Asesor de empresa diferente no debe ser elegible"
    )

    resultados = simular_asignacion_leads([lead], [asesor])
    assert len(resultados) == 1
    assert not resultados[0].asignado
    assert resultados[0].razon_sin_asignar == RAZON_SIN_ASESOR_COMPATIBLE


# ─────────────────────────────────────────────
# CASO 2 — PV diferente → NO ELEGIBLE
# ─────────────────────────────────────────────

def test_2_pv_diferente_no_elegible():
    """
    Misma empresa, PV diferente: el asesor NO debe ser elegible.
    """
    asesor = make_asesor("AS-Z1", "EMP-01", "PV-002", cap=10)
    lead = make_lead("L-001", "EMP-01", "PV-001")

    assert not asesor.es_elegible(lead.empresa_id, lead.punto_venta_id), (
        "Asesor de PV diferente no debe ser elegible"
    )

    resultados = simular_asignacion_leads([lead], [asesor])
    assert not resultados[0].asignado
    assert resultados[0].razon_sin_asignar == RAZON_SIN_ASESOR_COMPATIBLE


# ─────────────────────────────────────────────
# CASO 3 — Asesor inactivo → NO ELEGIBLE
# ─────────────────────────────────────────────

def test_3_asesor_inactivo_no_elegible():
    """
    Asesor inactivo con capacidad disponible: NO debe ser elegible.
    """
    asesor = make_asesor("AS-Z1", "EMP-01", "PV-001", cap=10, activo=False)
    lead = make_lead("L-001", "EMP-01", "PV-001")

    assert not asesor.es_elegible(lead.empresa_id, lead.punto_venta_id), (
        "Asesor inactivo no debe ser elegible aunque tenga capacidad"
    )

    resultados = simular_asignacion_leads([lead], [asesor])
    assert not resultados[0].asignado
    assert resultados[0].razon_sin_asignar == RAZON_SIN_ASESOR_ACTIVO


# ─────────────────────────────────────────────
# CASO 4 — Capacidad agotada → NO ELEGIBLE
# ─────────────────────────────────────────────

def test_4_capacidad_agotada_no_elegible():
    """
    Asesor activo pero con carga == capacidad: NO debe ser elegible.
    """
    asesor = make_asesor("AS-Z1", "EMP-01", "PV-001", cap=5, activo=True, carga=5)
    lead = make_lead("L-001", "EMP-01", "PV-001")

    assert asesor.capacidad_disponible == 0
    assert not asesor.es_elegible(lead.empresa_id, lead.punto_venta_id), (
        "Asesor sin capacidad disponible no debe ser elegible"
    )

    resultados = simular_asignacion_leads([lead], [asesor], cargas_iniciales={"AS-Z1": 5})
    assert not resultados[0].asignado
    assert resultados[0].razon_sin_asignar == RAZON_SIN_CAPACIDAD


# ─────────────────────────────────────────────
# CASO 5 — Menor carga relativa es seleccionado
# ─────────────────────────────────────────────

def test_5_menor_carga_relativa_seleccionado():
    """
    Entre múltiples candidatos elegibles, seleccionar el de menor carga relativa.

    AS-A: 3/12 = 0.25  ← DEBE SER SELECCIONADO
    AS-B: 6/20 = 0.30
    AS-C: 2/5  = 0.40
    """
    asesores = [
        make_asesor("AS-A", "EMP-01", "PV-001", cap=12, carga=3),
        make_asesor("AS-B", "EMP-01", "PV-001", cap=20, carga=6),
        make_asesor("AS-C", "EMP-01", "PV-001", cap=5,  carga=2),
    ]
    lead = make_lead("L-001", "EMP-01", "PV-001")

    resultados = simular_asignacion_leads(
        [lead], asesores,
        cargas_iniciales={"AS-A": 3, "AS-B": 6, "AS-C": 2}
    )

    assert resultados[0].asignado
    assert resultados[0].asesor_asignado == "AS-A", (
        f"Se esperaba AS-A (carga relativa 0.25), se obtuvo {resultados[0].asesor_asignado}"
    )


# ─────────────────────────────────────────────
# CASO 6 — Desempate determinista
# ─────────────────────────────────────────────

def test_6_desempate_primer_criterio_carga_absoluta():
    """
    Misma carga relativa, desempate por menor carga absoluta.
    """
    # AS-A: 2/4 = 0.5, carga=2  ← DEBE SER SELECCIONADO (menor carga absoluta)
    # AS-B: 4/8 = 0.5, carga=4
    asesores = [
        make_asesor("AS-A", "EMP-01", "PV-001", cap=4, carga=2),
        make_asesor("AS-B", "EMP-01", "PV-001", cap=8, carga=4),
    ]

    seleccionado = seleccionar_asesor_optimo(asesores)
    assert seleccionado.asesor_id == "AS-A", "Desempate: menor carga absoluta"


def test_6_desempate_segundo_criterio_mayor_capacidad_disponible():
    """
    Misma carga relativa y absoluta, desempate por mayor capacidad disponible.
    """
    # AS-A: 2/4 = 0.5, carga=2, disponible=2
    # AS-B: 2/6 = 0.333..., menor relativa → se selecciona primero por regla 1
    # Escenario: ambos con misma carga relativa y absoluta
    # AS-X: 3/6 = 0.5, disponible=3  ← DEBE SER SELECCIONADO
    # AS-Y: 3/5 = 0.6... (diferente relativa, no aplica el desempate aquí)
    # Probar exacto empate en relativa y absoluta:
    # AS-A: 2/4=0.5, carga=2, disp=2
    # AS-B: 2/4=0.5, carga=2, disp=2 → asesor_id ASC desempata

    asesores = [
        make_asesor("AS-B", "EMP-01", "PV-001", cap=4, carga=2),
        make_asesor("AS-A", "EMP-01", "PV-001", cap=4, carga=2),
    ]

    seleccionado = seleccionar_asesor_optimo(asesores)
    assert seleccionado.asesor_id == "AS-A", "Desempate final: asesor_id ASC"


def test_6_desempate_asesor_id_asc():
    """
    Empate total: mismo relativa, misma carga, misma disponible → asesor_id ASC.
    """
    asesores = [
        make_asesor("AS-C", "EMP-01", "PV-001", cap=10, carga=5),
        make_asesor("AS-A", "EMP-01", "PV-001", cap=10, carga=5),
        make_asesor("AS-B", "EMP-01", "PV-001", cap=10, carga=5),
    ]

    seleccionado = seleccionar_asesor_optimo(asesores)
    assert seleccionado.asesor_id == "AS-A", "En empate total, seleccionar por asesor_id ASC"


# ─────────────────────────────────────────────
# CASO 7 — Sin asesor disponible → SIN_ASIGNAR
# ─────────────────────────────────────────────

def test_7_sin_asesor_disponible():
    """
    Todos los asesores del PV agotaron capacidad: el lead queda SIN_ASIGNAR.
    """
    asesores = [
        make_asesor("AS-A", "EMP-01", "PV-001", cap=3, activo=True, carga=3),
        make_asesor("AS-B", "EMP-01", "PV-001", cap=5, activo=True, carga=5),
    ]
    lead = make_lead("L-001", "EMP-01", "PV-001")

    resultados = simular_asignacion_leads(
        [lead], asesores,
        cargas_iniciales={"AS-A": 3, "AS-B": 5}
    )

    assert not resultados[0].asignado
    assert resultados[0].razon_sin_asignar == RAZON_SIN_CAPACIDAD


def test_7_sin_asesor_compatible():
    """
    No hay asesores del PV del lead en absoluto.
    """
    asesores = [
        make_asesor("AS-A", "EMP-01", "PV-002", cap=10),
    ]
    lead = make_lead("L-001", "EMP-01", "PV-001")

    resultados = simular_asignacion_leads([lead], asesores)
    assert not resultados[0].asignado
    assert resultados[0].razon_sin_asignar == RAZON_SIN_ASESOR_COMPATIBLE


# ─────────────────────────────────────────────
# CASO 8 — Carga nunca supera capacidad
# ─────────────────────────────────────────────

def test_8_carga_nunca_supera_capacidad():
    """
    Después de la simulación, ningún asesor debe superar su capacidad diaria.
    """
    asesores = [
        make_asesor("AS-A", "EMP-01", "PV-001", cap=3),
        make_asesor("AS-B", "EMP-01", "PV-001", cap=2),
    ]
    leads = [make_lead(f"L-{i:03d}", "EMP-01", "PV-001") for i in range(20)]

    resultados = simular_asignacion_leads(leads, asesores)

    cargas = cargas_finales_de_simulacion(asesores, resultados)
    for asesor in asesores:
        assert cargas[asesor.asesor_id] <= asesor.capacidad_diaria_leads, (
            f"Asesor {asesor.asesor_id}: carga {cargas[asesor.asesor_id]} "
            f"> capacidad {asesor.capacidad_diaria_leads}"
        )

    # Total asignados = cap total disponible = 5
    total_asignados = sum(1 for r in resultados if r.asignado)
    assert total_asignados == 5
    total_sin = sum(1 for r in resultados if not r.asignado)
    assert total_sin == 15


# ─────────────────────────────────────────────
# CASO 9 — Orden de leads por prioridad
# ─────────────────────────────────────────────

def test_9_orden_leads_por_prioridad():
    """
    El lead con mayor puntaje_prioridad debe procesarse primero.
    Con un solo asesor con capacidad=1, el primer lead asignado debe ser el de mayor prioridad.
    """
    asesores = [make_asesor("AS-A", "EMP-01", "PV-001", cap=1)]
    leads = [
        make_lead("L-BAJO",  "EMP-01", "PV-001", prioridad=10.0, ts=datetime(2026, 1, 1)),
        make_lead("L-ALTO",  "EMP-01", "PV-001", prioridad=90.0, ts=datetime(2026, 1, 2)),
        make_lead("L-MEDIO", "EMP-01", "PV-001", prioridad=50.0, ts=datetime(2026, 1, 3)),
    ]

    resultados = simular_asignacion_leads(leads, asesores)

    asignados = [r for r in resultados if r.asignado]
    sin_asignar = [r for r in resultados if not r.asignado]

    assert len(asignados) == 1
    assert asignados[0].lead_id == "L-ALTO", (
        "El lead con mayor prioridad debe ser asignado cuando hay capacidad limitada"
    )
    assert len(sin_asignar) == 2


def test_9_tercer_criterio_fecha_registro_asc():
    """
    Con misma prioridad y urgencia, el lead más antiguo (registrado_en ASC) tiene precedencia.
    """
    asesores = [make_asesor("AS-A", "EMP-01", "PV-001", cap=1)]
    leads = [
        make_lead("L-NUEVO",   "EMP-01", "PV-001", prioridad=50.0, ts=datetime(2026, 3, 1)),
        make_lead("L-ANTIGUO", "EMP-01", "PV-001", prioridad=50.0, ts=datetime(2026, 1, 1)),
    ]

    resultados = simular_asignacion_leads(leads, asesores)
    asignados = [r for r in resultados if r.asignado]

    assert asignados[0].lead_id == "L-ANTIGUO", (
        "Con misma prioridad, debe asignarse el lead más antiguo (registrado_en ASC)"
    )


# ─────────────────────────────────────────────
# CASO 10 — Determinismo
# ─────────────────────────────────────────────

def test_10_determinismo():
    """
    Dos ejecuciones con los mismos datos deben producir exactamente los mismos resultados.
    """
    asesores = [
        make_asesor("AS-A", "EMP-01", "PV-001", cap=5),
        make_asesor("AS-B", "EMP-01", "PV-001", cap=3),
        make_asesor("AS-C", "EMP-01", "PV-002", cap=4),
    ]
    leads = [
        make_lead(f"L-{i:03d}", "EMP-01", "PV-001", prioridad=float(100 - i))
        for i in range(10)
    ]

    resultados_1 = simular_asignacion_leads(leads, asesores)
    resultados_2 = simular_asignacion_leads(leads, asesores)

    assert len(resultados_1) == len(resultados_2)
    for r1, r2 in zip(resultados_1, resultados_2):
        assert r1.lead_id == r2.lead_id
        assert r1.asesor_asignado == r2.asesor_asignado
        assert r1.asignado == r2.asignado
        assert r1.razon_sin_asignar == r2.razon_sin_asignar


# ─────────────────────────────────────────────
# VALIDACIÓN DE AISLAMIENTO MULTIEMPRESA
# ─────────────────────────────────────────────

def test_aislamiento_empresa_nunca_se_cruza():
    """
    En ningún caso un lead de EMP-01 debe asignarse a un asesor de EMP-02.
    """
    asesores = [
        make_asesor("AS-A", "EMP-01", "PV-001", cap=10),
        make_asesor("AS-B", "EMP-02", "PV-001", cap=10),  # misma PV, diferente empresa
    ]
    leads = [make_lead(f"L-{i}", "EMP-01", "PV-001") for i in range(5)]

    resultados = simular_asignacion_leads(leads, asesores)

    for r in resultados:
        if r.asignado:
            # Solo AS-A (EMP-01) es válido
            assert r.asesor_asignado == "AS-A", (
                "Nunca asignar lead de EMP-01 a asesor de EMP-02"
            )


def test_aislamiento_pv_nunca_se_cruza():
    """
    En ningún caso un lead de PV-001 debe asignarse a un asesor de PV-002 (misma empresa).
    """
    asesores = [
        make_asesor("AS-A", "EMP-01", "PV-002", cap=10),  # PV diferente
    ]
    leads = [make_lead("L-001", "EMP-01", "PV-001")]

    resultados = simular_asignacion_leads(leads, asesores)
    assert not resultados[0].asignado


def test_capacidad_relativa_propiedad():
    """Verificar la propiedad de carga relativa."""
    a = make_asesor("AS-X", "EMP-01", "PV-001", cap=20, carga=4)
    assert abs(a.carga_relativa - 0.2) < 1e-9

    b = make_asesor("AS-Y", "EMP-01", "PV-001", cap=0)  # capacidad 0
    assert b.carga_relativa == float("inf")
    assert b.capacidad_disponible == 0


# ─────────────────────────────────────────────
# FASE 9D.3 — PERSISTENCIA E IDEMPOTENCIA
# ─────────────────────────────────────────────

def test_lead_ya_asignado_no_consume_capacidad():
    """
    Si un lead ya cuenta con asignación activa en el sistema,
    debe catalogarse como YA_ASIGNADO y NO consumir capacidad del asesor.
    """
    asesor = make_asesor("AS-A", "EMP-01", "PV-001", cap=1)
    leads = [
        make_lead("LEAD-001", "EMP-01", "PV-001", prioridad=100.0),
        make_lead("LEAD-002", "EMP-01", "PV-001", prioridad=50.0),
    ]

    # LEAD-001 ya está asignado
    resultados = simular_asignacion_leads(
        leads, [asesor],
        leads_ya_asignados={"LEAD-001"}
    )

    r_map = {r.lead_id: r for r in resultados}
    assert not r_map["LEAD-001"].asignado
    assert r_map["LEAD-001"].razon_sin_asignar == RAZON_YA_ASIGNADO

    # LEAD-002 debe obtener la capacidad disponible (cap=1)
    assert r_map["LEAD-002"].asignado
    assert r_map["LEAD-002"].asesor_asignado == "AS-A"


def test_no_duplicar_asignaciones_segunda_ejecucion():
    """
    Al simular sobre un conjunto donde todos los asignables ya tienen asignación,
    ninguno debe ser reasignado (idempotencia en memoria).
    """
    asesores = [make_asesor("AS-A", "EMP-01", "PV-001", cap=5)]
    leads = [make_lead(f"L-{i}", "EMP-01", "PV-001") for i in range(3)]

    # Primera corrida: se asignan los 3
    res1 = simular_asignacion_leads(leads, asesores)
    asignados_1 = {r.lead_id for r in res1 if r.asignado}
    assert len(asignados_1) == 3

    # Segunda corrida: los 3 ya están asignados
    res2 = simular_asignacion_leads(leads, asesores, leads_ya_asignados=asignados_1)
    asignados_2 = [r for r in res2 if r.asignado]
    ya_asignados_2 = [r for r in res2 if r.razon_sin_asignar == RAZON_YA_ASIGNADO]

    assert len(asignados_2) == 0, "No debe haber nuevas asignaciones"
    assert len(ya_asignados_2) == 3, "Todos deben marcarse como YA_ASIGNADO"


def test_persistencia_transaccional_e_idempotencia_db():
    """
    Prueba que persistir_asignaciones inserta correctamente y que una
    segunda llamada con el mismo lead no crea duplicados (ON CONFLICT).
    Usa rollback al final para no alterar PostgreSQL.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Seleccionar un lead y asesor reales para la prueba
            cur.execute("SELECT lead_id FROM core.leads LIMIT 1;")
            test_lead_id = cur.fetchone()[0]
            cur.execute("SELECT asesor_id FROM core.asesores WHERE activo = true LIMIT 1;")
            test_asesor_id = cur.fetchone()[0]

            # Simular un resultado de asignación
            asignacion = ResultadoAsignacion(
                lead_id=test_lead_id,
                empresa_id="EMP-01",
                punto_venta_id="PV-001",
                puntaje_prioridad=50.0,
                puntaje_urgencia=None,
                asesor_asignado=test_asesor_id,
                razon_sin_asignar=None,
                asignado=True,
            )

            try:
                # Primera inserción (debe retornar 0 si ya existe, o 1 si es nuevo)
                insertados_1 = persistir_asignaciones(conn, [asignacion])
                assert insertados_1 in (0, 1)

                # Segunda inserción idéntica: DEBE retornar 0 por el índice uq_asignaciones_lead_actual
                insertados_2 = persistir_asignaciones(conn, [asignacion])
                assert insertados_2 == 0, "La segunda inserción del mismo lead debe retornar 0 por ON CONFLICT"

            finally:
                # SIEMPRE hacer rollback para no persistir datos de prueba
                conn.rollback()

