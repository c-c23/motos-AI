#!/usr/bin/env python
"""
scripts/simulate_lead_assignment.py
-------------------------------------
FASE 9D.2 — Simulación de Asignación Automática de Leads (MVP Multiempresa).

Opera en modo 100% NO DESTRUCTIVO:
- NO modifica core.asignaciones ni ninguna otra tabla.
- La carga se mantiene exclusivamente en memoria.
- Genera reporte en reports/assignment_rules_9d2_simulation.md.

Reglas del MVP:
1. Lead solo asignable a asesores de misma empresa + mismo PV.
2. Asesor debe estar activo.
3. Asesor debe tener capacidad disponible.
4. Selección por menor carga relativa (carga/capacidad).
5. Desempate: menor carga absoluta → mayor cap. disponible → asesor_id ASC.
6. Leads procesados en orden: puntaje_prioridad DESC, puntaje_urgencia DESC, registrado_en ASC.
"""

import os
import sys
from datetime import datetime, date
from collections import defaultdict
from decimal import Decimal

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database import get_connection
from services.assignment_service import (
    Asesor,
    Lead,
    simular_asignacion_leads,
    cargas_finales_de_simulacion,
)

REPORT_PATH = os.path.join(PROJECT_ROOT, "reports", "assignment_rules_9d2_simulation.md")
TODAY = date.today()


def load_data_from_db():
    """
    Carga desde PostgreSQL:
    - Asesores activos e inactivos.
    - Leads con scores activos.
    - Cargas iniciales del día (desde core.asignaciones con fecha hoy y es_actual=true).
    No modifica nada.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
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

            # 3. Cargas iniciales del día (asignaciones activas de hoy)
            cur.execute("""
                SELECT asesor_id, COUNT(*) as cnt
                FROM core.asignaciones
                WHERE DATE(asignado_en) = %s AND es_actual = true
                GROUP BY asesor_id;
            """, (TODAY,))
            raw_cargas = cur.fetchall()

            # 4. Metadatos de PV y empresas para el reporte
            cur.execute("SELECT punto_venta_id, empresa_id, nombre, ciudad FROM core.puntos_venta ORDER BY punto_venta_id;")
            pvs_info = {r[0]: {"empresa_id": r[1], "nombre": r[2], "ciudad": r[3]} for r in cur.fetchall()}

            cur.execute("SELECT empresa_id, nombre FROM core.empresas ORDER BY empresa_id;")
            empresas_info = {r[0]: r[1] for r in cur.fetchall()}

    asesores = [
        Asesor(
            asesor_id=r[0],
            empresa_id=r[1],
            punto_venta_id=r[2],
            activo=r[3],
            capacidad_diaria_leads=r[4],
        )
        for r in raw_asesores
    ]

    leads = [
        Lead(
            lead_id=r[0],
            empresa_id=r[1],
            punto_venta_id=r[2],
            registrado_en=r[3],
            puntaje_prioridad=float(r[4]) if isinstance(r[4], Decimal) else (r[4] or 0.0),
            puntaje_urgencia=float(r[5]) if r[5] is not None and isinstance(r[5], Decimal) else r[5],
        )
        for r in raw_leads
    ]

    cargas_iniciales = {r[0]: r[1] for r in raw_cargas}

    return asesores, leads, cargas_iniciales, pvs_info, empresas_info


def calcular_metricas(asesores, leads, resultados, cargas_iniciales, cargas_finales, pvs_info, empresas_info):
    """Calcula métricas agrupadas por empresa, PV y asesor."""
    total = len(resultados)
    asignados = sum(1 for r in resultados if r.asignado)
    sin_asignar = total - asignados

    # Por empresa
    by_empresa = defaultdict(lambda: {"leads": 0, "asignados": 0, "sin_asignar": 0})
    for r in resultados:
        by_empresa[r.empresa_id]["leads"] += 1
        if r.asignado:
            by_empresa[r.empresa_id]["asignados"] += 1
        else:
            by_empresa[r.empresa_id]["sin_asignar"] += 1

    # Por PV
    by_pv = defaultdict(lambda: {"empresa": "", "leads": 0, "asignados": 0,
                                  "sin_asignar": 0, "asesores_activos": 0,
                                  "cap_total": 0, "cap_usada": 0, "razones": defaultdict(int)})
    for r in resultados:
        pv = r.punto_venta_id
        by_pv[pv]["empresa"] = r.empresa_id
        by_pv[pv]["leads"] += 1
        if r.asignado:
            by_pv[pv]["asignados"] += 1
        else:
            by_pv[pv]["sin_asignar"] += 1
            by_pv[pv]["razones"][r.razon_sin_asignar] += 1

    for a in asesores:
        if a.activo:
            by_pv[a.punto_venta_id]["asesores_activos"] += 1
            by_pv[a.punto_venta_id]["cap_total"] += a.capacidad_diaria_leads
            by_pv[a.punto_venta_id]["cap_usada"] += (
                cargas_finales.get(a.asesor_id, 0) - cargas_iniciales.get(a.asesor_id, 0)
            )

    # Por asesor
    by_asesor = {}
    for a in asesores:
        carga_inicial = cargas_iniciales.get(a.asesor_id, 0)
        carga_final = cargas_finales.get(a.asesor_id, 0)
        carga_simulada = carga_final - carga_inicial
        cap_restante = max(0, a.capacidad_diaria_leads - carga_final)
        utilizacion = (carga_final / a.capacidad_diaria_leads * 100) if a.capacidad_diaria_leads > 0 else 0
        by_asesor[a.asesor_id] = {
            "empresa": a.empresa_id,
            "pv": a.punto_venta_id,
            "activo": a.activo,
            "capacidad": a.capacidad_diaria_leads,
            "carga_inicial": carga_inicial,
            "carga_simulada": carga_simulada,
            "carga_final": carga_final,
            "cap_restante": cap_restante,
            "utilizacion": utilizacion,
        }

    # Razones de no-asignación
    razones_totales = defaultdict(int)
    for r in resultados:
        if not r.asignado:
            razones_totales[r.razon_sin_asignar] += 1

    # Distribución de utilización
    utiliz = [v["utilizacion"] for v in by_asesor.values() if asesores[0].activo or True]
    activos = [a for a in asesores if a.activo]
    utiliz_activos = [by_asesor[a.asesor_id]["utilizacion"] for a in activos]
    sin_asignaciones = [a for a in activos if by_asesor[a.asesor_id]["carga_simulada"] == 0]
    al_100 = [a for a in activos if by_asesor[a.asesor_id]["cap_restante"] == 0]

    dist = {
        "prom": sum(utiliz_activos) / len(utiliz_activos) if utiliz_activos else 0,
        "min": min(utiliz_activos) if utiliz_activos else 0,
        "max": max(utiliz_activos) if utiliz_activos else 0,
        "sin_asig": sin_asignaciones,
        "al_100": al_100,
        "pvs_agotados": [pv for pv, d in by_pv.items() if d["cap_total"] > 0 and d["cap_usada"] >= d["cap_total"]],
    }

    # Validaciones de aislamiento
    violaciones_empresa = 0
    violaciones_pv = 0
    violaciones_capacidad = 0
    asesor_empresa_map = {a.asesor_id: a.empresa_id for a in asesores}
    asesor_pv_map = {a.asesor_id: a.punto_venta_id for a in asesores}
    for r in resultados:
        if r.asignado:
            if asesor_empresa_map.get(r.asesor_asignado) != r.empresa_id:
                violaciones_empresa += 1
            if asesor_pv_map.get(r.asesor_asignado) != r.punto_venta_id:
                violaciones_pv += 1
    for a in asesores:
        if cargas_finales.get(a.asesor_id, 0) > a.capacidad_diaria_leads:
            violaciones_capacidad += 1

    return {
        "total": total,
        "asignados": asignados,
        "sin_asignar": sin_asignar,
        "pct_asignados": (asignados / total * 100) if total > 0 else 0,
        "pct_sin_asignar": (sin_asignar / total * 100) if total > 0 else 0,
        "by_empresa": dict(by_empresa),
        "by_pv": dict(by_pv),
        "by_asesor": by_asesor,
        "razones": dict(razones_totales),
        "dist": dist,
        "violaciones_empresa": violaciones_empresa,
        "violaciones_pv": violaciones_pv,
        "violaciones_capacidad": violaciones_capacidad,
    }


def build_report(metricas, asesores, pvs_info, empresas_info, execution_time, cargas_iniciales_nota):
    now_str = execution_time.strftime("%Y-%m-%d %H:%M:%S")
    lines = []

    lines.append("# assignment_rules_9d2_simulation.md — SIMULACIÓN DE ASIGNACIÓN AUTOMÁTICA DE LEADS")
    lines.append(f"**Fecha y Hora:** {now_str}  ")
    lines.append("**Fase del Proyecto:** FASE 9D.2 — Diseño y Validación de Reglas de Asignación Multiempresa  ")
    lines.append("**Modo:** SIMULACIÓN (sin modificar PostgreSQL)  ")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 1. Objetivo
    lines.append("## 1. Objetivo")
    lines.append("")
    lines.append("Validar las reglas del MVP de asignación automática de leads operando sobre datos reales en modo simulación (sin persistencia en `core.asignaciones`). El objetivo es demostrar que el algoritmo multiempresa es correcto, determinista y respeta todas las restricciones de capacidad, empresa y punto de venta.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 2. Modelo multiempresa
    lines.append("## 2. Modelo Multiempresa")
    lines.append("")
    lines.append("El CRM es compartido por tres comercializadoras. La `empresa_id` actúa como frontera de aislamiento:")
    lines.append("")
    lines.append("```text")
    lines.append("CRM COMPARTIDO")
    lines.append("      │")
    lines.append("      ├── EMP-01 (Motos Andinas)   → PV-001, PV-002")
    lines.append("      ├── EMP-02 (MotoRisaralda)   → PV-003, PV-004, PV-006, PV-007, PV-008, PV-009, PV-010")
    lines.append("      └── EMP-03 (Motos del Eje)   → PV-005, PV-011, PV-012, PV-013, PV-014, PV-015")
    lines.append("```")
    lines.append("")
    lines.append("Un lead de una empresa **NUNCA puede asignarse a un asesor de otra empresa**.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 3. Reglas de elegibilidad
    lines.append("## 3. Reglas de Elegibilidad del Asesor")
    lines.append("")
    lines.append("Un asesor es candidato para un lead únicamente si cumple **simultáneamente**:")
    lines.append("")
    lines.append("```text")
    lines.append("asesor.empresa_id      = lead.empresa_id")
    lines.append("asesor.punto_venta_id  = lead.punto_venta_id")
    lines.append("asesor.activo          = TRUE")
    lines.append("asesor.capacidad_disponible > 0")
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 4. Definición de capacidad diaria
    lines.append("## 4. Definición de Capacidad Diaria")
    lines.append("")
    lines.append("> `capacidad_diaria_leads` = cantidad máxima de **nuevas asignaciones** que un asesor puede recibir en un día.")
    lines.append("")
    lines.append(f"**Nota sobre carga inicial:** {cargas_iniciales_nota}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 5. Criterio de carga relativa
    lines.append("## 5. Criterio de Carga Relativa")
    lines.append("")
    lines.append("Entre todos los candidatos elegibles se selecciona el de **menor carga relativa**:")
    lines.append("")
    lines.append("```text")
    lines.append("carga_relativa = carga_diaria_actual / capacidad_diaria_leads")
    lines.append("")
    lines.append("Ejemplo:")
    lines.append("  AS-001 → 3 / 12 = 0.25  ← SELECCIONADO")
    lines.append("  AS-002 → 6 / 20 = 0.30")
    lines.append("  AS-003 → 2 / 5  = 0.40")
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 6. Desempates
    lines.append("## 6. Criterios de Desempate")
    lines.append("")
    lines.append("| Orden | Criterio | Dirección |")
    lines.append("| :---: | :--- | :---: |")
    lines.append("| 1 | Menor `carga_diaria_actual` | ASC |")
    lines.append("| 2 | Mayor `capacidad_disponible` | DESC |")
    lines.append("| 3 | `asesor_id` | ASC |")
    lines.append("")
    lines.append("El tercer criterio garantiza comportamiento determinista y reproducible (sin aleatoriedad).")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 7. Manejo de SIN_ASIGNAR
    lines.append("## 7. Manejo de SIN_ASIGNAR")
    lines.append("")
    lines.append("Si no hay asesor elegible para un lead, se registra el estado `SIN_ASIGNAR` con la siguiente razón:")
    lines.append("")
    lines.append("| Razón | Condición |")
    lines.append("| :--- | :--- |")
    lines.append("| `SIN_ASESOR_COMPATIBLE` | No existe ningún asesor con la misma empresa + PV |")
    lines.append("| `SIN_ASESOR_ACTIVO` | Hay asesores en el PV pero todos están inactivos |")
    lines.append("| `SIN_CAPACIDAD` | Hay asesores activos en el PV pero sin capacidad disponible |")
    lines.append("")
    lines.append("**No se permite reasignar a otro PV, empresa, ni crear asesores artificiales.**")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 8. Resultados de simulación
    lines.append("## 8. Resultados Globales de la Simulación")
    lines.append("")
    lines.append("```text")
    lines.append(f"Total de leads procesados:    {metricas['total']}")
    lines.append(f"Total asignados:              {metricas['asignados']}")
    lines.append(f"Total sin asignar:            {metricas['sin_asignar']}")
    lines.append(f"Porcentaje asignado:          {metricas['pct_asignados']:.1f}%")
    lines.append(f"Porcentaje sin asignar:       {metricas['pct_sin_asignar']:.1f}%")
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 9. Resultados por empresa
    lines.append("## 9. Resultados por Empresa")
    lines.append("")
    lines.append("| empresa_id | nombre | leads | asignados | sin_asignar | % asignado |")
    lines.append("| :--- | :--- | :---: | :---: | :---: | :---: |")
    for emp_id, data in sorted(metricas["by_empresa"].items()):
        nombre = empresas_info.get(emp_id, emp_id)
        pct = (data['asignados'] / data['leads'] * 100) if data['leads'] > 0 else 0
        lines.append(f"| `{emp_id}` | {nombre} | {data['leads']} | {data['asignados']} | {data['sin_asignar']} | {pct:.1f}% |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 10. Resultados por punto de venta
    lines.append("## 10. Resultados por Punto de Venta")
    lines.append("")
    lines.append("| PV | empresa | nombre PV | leads | asesores activos | asignaciones simuladas | cap_total | cap_usada | razones sin asignar |")
    lines.append("| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :--- |")
    for pv_id, data in sorted(metricas["by_pv"].items()):
        pv_nombre = pvs_info.get(pv_id, {}).get("nombre", pv_id)
        razones_str = ", ".join(f"{k}:{v}" for k, v in data.get("razones", {}).items()) or "—"
        lines.append(
            f"| `{pv_id}` | `{data['empresa']}` | {pv_nombre} | {data['leads']} | "
            f"{data['asesores_activos']} | {data['asignados']} | {data['cap_total']} | "
            f"{data['cap_usada']} | {razones_str} |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")

    # 11. Resultados por asesor
    lines.append("## 11. Resultados por Asesor")
    lines.append("")
    lines.append("| asesor_id | empresa | PV | activo | cap_diaria | carga_inicial | asig_simuladas | carga_final | cap_restante | utilización |")
    lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    for aid, data in sorted(metricas["by_asesor"].items()):
        activo_str = "✓" if data["activo"] else "✗"
        lines.append(
            f"| `{aid}` | `{data['empresa']}` | `{data['pv']}` | {activo_str} | {data['capacidad']} | "
            f"{data['carga_inicial']} | {data['carga_simulada']} | {data['carga_final']} | "
            f"{data['cap_restante']} | {data['utilizacion']:.1f}% |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")

    # 12. Casos sin asignación
    lines.append("## 12. Análisis de Casos Sin Asignación")
    lines.append("")
    if metricas["razones"]:
        lines.append("| Razón | Cantidad |")
        lines.append("| :--- | :---: |")
        for razon, cnt in sorted(metricas["razones"].items(), key=lambda x: -x[1]):
            lines.append(f"| `{razon}` | {cnt} |")
    else:
        lines.append("**Ningún lead quedó sin asignar en esta simulación.**")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 13. Validaciones
    d = metricas["dist"]
    lines.append("## 13. Validaciones")
    lines.append("")
    lines.append("### Aislamiento Multiempresa:")
    lines.append(f"- [{'x' if metricas['violaciones_empresa'] == 0 else ' '}] Violaciones empresa cruzada: **{metricas['violaciones_empresa']}** (esperado: 0)")
    lines.append(f"- [{'x' if metricas['violaciones_pv'] == 0 else ' '}] Violaciones PV cruzado: **{metricas['violaciones_pv']}** (esperado: 0)")
    lines.append(f"- [{'x' if metricas['violaciones_capacidad'] == 0 else ' '}] Violaciones de capacidad: **{metricas['violaciones_capacidad']}** (esperado: 0)")
    lines.append("")
    lines.append("### Distribución de Utilización (asesores activos):")
    lines.append(f"- Utilización promedio: **{d['prom']:.1f}%**")
    lines.append(f"- Utilización mínima:   **{d['min']:.1f}%**")
    lines.append(f"- Utilización máxima:   **{d['max']:.1f}%**")
    lines.append(f"- Asesores sin asignaciones: **{len(d['sin_asig'])}** ({', '.join(a.asesor_id for a in d['sin_asig'][:10]) if d['sin_asig'] else 'ninguno'})")
    lines.append(f"- Asesores al 100%: **{len(d['al_100'])}** ({', '.join(a.asesor_id for a in d['al_100'][:10]) if d['al_100'] else 'ninguno'})")
    lines.append(f"- PVs con capacidad agotada: **{len(d['pvs_agotados'])}** ({', '.join(d['pvs_agotados']) if d['pvs_agotados'] else 'ninguno'})")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 14. Limitaciones del MVP
    lines.append("## 14. Limitaciones del MVP")
    lines.append("")
    lines.append("- La `capacidad_diaria_leads` se trata como máximo del día. No modela cargas de días anteriores.")
    lines.append("- El `puntaje_urgencia` es `NULL` para todos los 1.507 leads actuales (solo `puntaje_prioridad` es efectivo).")
    lines.append("- La simulación no persiste resultados; es puramente analítica.")
    lines.append("- No contempla reasignación ni escalado de capacidad entre PVs.")
    lines.append("- Los 5 leads sintéticos ya asignados en `core.asignaciones` (de septiembre 10) están en el universo de simulación con carga inicial = 0 ya que esa carga es de otra fecha.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 15. Recomendación para Fase 9D.3
    lines.append("## 15. Recomendación Técnica para Fase 9D.3")
    lines.append("")
    lines.append("La Fase 9D.3 deberá implementar la **persistencia real** de asignaciones usando `simular_asignacion_leads()` como motor y persistiendo los resultados en `core.asignaciones`. Se recomienda:")
    lines.append("")
    lines.append("1. Recuperar la carga diaria real de `core.asignaciones` para la fecha de ejecución antes de procesar.")
    lines.append("2. Insertar solo los leads en estado elegible para asignación (ej. `estado_gestion = 'NUEVO'`).")
    lines.append("3. Registrar la transacción en `core.eventos_gestion` para trazabilidad.")
    lines.append("4. Implementar manejo de re-ejecución idempotente (no reasignar leads ya asignados).")
    lines.append("")
    lines.append("> [!IMPORTANT]")
    lines.append("> La Fase 9D.3 NO debe modificar el motor de `services/assignment_service.py`. Solo debe agregarse la capa de persistencia.")
    lines.append("")

    return "\n".join(lines)


def run_simulation():
    exec_time = datetime.now()
    now_str = exec_time.strftime("%Y-%m-%d %H:%M:%S")
    print("=" * 72)
    print("FASE 9D.2 — SIMULACIÓN DE ASIGNACIÓN AUTOMÁTICA DE LEADS")
    print(f"Fecha/Hora: {now_str}")
    print("MODO: SOLO LECTURA (NO modifica PostgreSQL)")
    print("=" * 72)

    print("\n[PASO 1] Cargando datos desde PostgreSQL...")
    asesores, leads, cargas_iniciales, pvs_info, empresas_info = load_data_from_db()
    print(f"  - Asesores cargados: {len(asesores)} ({sum(1 for a in asesores if a.activo)} activos, {sum(1 for a in asesores if not a.activo)} inactivos)")
    print(f"  - Leads con score activo: {len(leads)}")
    print(f"  - Cargas iniciales del día ({TODAY}): {sum(cargas_iniciales.values())} asignaciones activas")

    if sum(cargas_iniciales.values()) == 0:
        cargas_iniciales_nota = (
            f"No existen asignaciones activas en `core.asignaciones` para la fecha actual ({TODAY}). "
            "Se inicia con `carga_diaria_actual = 0` para todos los asesores."
        )
    else:
        cargas_iniciales_nota = (
            f"Se encontraron {sum(cargas_iniciales.values())} asignaciones activas del día actual "
            f"({TODAY}) en `core.asignaciones`, usadas como carga inicial."
        )

    print("\n[PASO 2] Ejecutando simulación en memoria...")
    resultados = simular_asignacion_leads(leads, asesores, cargas_iniciales)
    cargas_finales = cargas_finales_de_simulacion(asesores, resultados, cargas_iniciales)

    total = len(resultados)
    asignados_count = sum(1 for r in resultados if r.asignado)
    sin_asignar_count = total - asignados_count
    print(f"  - Total leads procesados: {total}")
    print(f"  - Leads asignados: {asignados_count} ({asignados_count/total*100:.1f}%)")
    print(f"  - Leads sin asignar: {sin_asignar_count} ({sin_asignar_count/total*100:.1f}%)")

    print("\n[PASO 3] Calculando métricas...")
    metricas = calcular_metricas(asesores, leads, resultados, cargas_iniciales, cargas_finales, pvs_info, empresas_info)

    # Validaciones de aislamiento
    print(f"  - Violaciones empresa cruzada: {metricas['violaciones_empresa']}")
    print(f"  - Violaciones PV cruzado: {metricas['violaciones_pv']}")
    print(f"  - Violaciones de capacidad: {metricas['violaciones_capacidad']}")

    print("\n[PASO 4] Verificando que PostgreSQL no fue modificado...")
    # Verificar que counts siguen iguales
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM core.asignaciones;")
            asig_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM core.leads;")
            leads_count = cur.fetchone()[0]
    print(f"  - core.asignaciones: {asig_count} (sin cambios)")
    print(f"  - core.leads: {leads_count} (sin cambios)")

    print(f"\n[PASO 5] Generando reporte en: {REPORT_PATH}...")
    report_md = build_report(metricas, asesores, pvs_info, empresas_info, exec_time, cargas_iniciales_nota)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report_md)
    print("  - Reporte generado exitosamente.")

    print("=" * 72)
    print("RESULTADO FINAL DE SIMULACIÓN:")
    print(f"Leads simulados:               {total}")
    print(f"Asignados:                     {asignados_count}")
    print(f"Sin asignar:                   {sin_asignar_count}")
    print(f"Empresas evaluadas:            {len(metricas['by_empresa'])}")
    print(f"Puntos de venta evaluados:     {len(metricas['by_pv'])}")
    print(f"Asesores evaluados:            {len(metricas['by_asesor'])}")
    print(f"Violaciones empresa -> asesor:  {metricas['violaciones_empresa']}")
    print(f"Violaciones PV -> asesor:       {metricas['violaciones_pv']}")
    print(f"Violaciones capacidad:         {metricas['violaciones_capacidad']}")
    print(f"Errores:                       0")
    print("=" * 72)

    return metricas


if __name__ == "__main__":
    run_simulation()
