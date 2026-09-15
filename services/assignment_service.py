"""
services/assignment_service.py
-------------------------------
Motor de asignación automática de leads — MVP Fase 9D.2.

Reglas:
- Un lead solo puede asignarse a un asesor de la MISMA empresa y el MISMO punto de venta.
- El asesor debe estar activo (activo = TRUE).
- El asesor debe tener capacidad disponible (carga_diaria_actual < capacidad_diaria_leads).
- Se selecciona el asesor con MENOR carga relativa (carga / capacidad).
- Desempate: menor carga absoluta → mayor capacidad disponible → asesor_id ASC.
- Si no hay asesor elegible, el lead queda SIN_ASIGNAR con razón documentada.

Este módulo NO modifica PostgreSQL. Operar en modo SIMULACIÓN.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ─────────────────────────────────────────────
# Estructuras de Datos
# ─────────────────────────────────────────────

@dataclass
class Asesor:
    asesor_id: str
    empresa_id: str
    punto_venta_id: str
    activo: bool
    capacidad_diaria_leads: int
    carga_diaria: int = 0  # carga actual del día (en memoria)

    @property
    def capacidad_disponible(self) -> int:
        return max(0, self.capacidad_diaria_leads - self.carga_diaria)

    @property
    def carga_relativa(self) -> float:
        if self.capacidad_diaria_leads == 0:
            return float("inf")
        return self.carga_diaria / self.capacidad_diaria_leads

    def es_elegible(self, empresa_id: str, punto_venta_id: str) -> bool:
        """Verifica si el asesor es elegible para un lead dado."""
        return (
            self.activo
            and self.empresa_id == empresa_id
            and self.punto_venta_id == punto_venta_id
            and self.capacidad_disponible > 0
        )


@dataclass
class Lead:
    lead_id: str
    empresa_id: str
    punto_venta_id: str
    puntaje_prioridad: float
    puntaje_urgencia: Optional[float]
    registrado_en: object  # datetime


@dataclass
class ResultadoAsignacion:
    lead_id: str
    empresa_id: str
    punto_venta_id: str
    puntaje_prioridad: float
    puntaje_urgencia: Optional[float]
    asesor_asignado: Optional[str]
    razon_sin_asignar: Optional[str]
    asignado: bool

    @property
    def estado(self) -> str:
        return "ASIGNADO" if self.asignado else "SIN_ASIGNAR"


# ─────────────────────────────────────────────
# Razones de No-Asignación
# ─────────────────────────────────────────────

RAZON_SIN_ASESOR_ACTIVO = "SIN_ASESOR_ACTIVO"
RAZON_SIN_CAPACIDAD = "SIN_CAPACIDAD"
RAZON_SIN_ASESOR_COMPATIBLE = "SIN_ASESOR_COMPATIBLE"
RAZON_DATOS_INCOMPLETOS = "DATOS_INCOMPLETOS"
RAZON_YA_ASIGNADO = "YA_ASIGNADO"


# ─────────────────────────────────────────────
# Funciones del Motor
# ─────────────────────────────────────────────

def ordenar_leads_por_prioridad(leads: List[Lead]) -> List[Lead]:
    """
    Ordena leads por:
    1. puntaje_prioridad DESC
    2. puntaje_urgencia DESC (NULL al final)
    3. registrado_en ASC
    """
    def sort_key(lead: Lead) -> Tuple:
        urgencia = lead.puntaje_urgencia if lead.puntaje_urgencia is not None else -float("inf")
        return (-lead.puntaje_prioridad, -urgencia, lead.registrado_en)

    return sorted(leads, key=sort_key)


def seleccionar_asesor_optimo(
    candidatos: List[Asesor],
) -> Optional[Asesor]:
    """
    Selecciona el mejor asesor de una lista de candidatos elegibles usando:
    1. Menor carga relativa (carga / capacidad)
    2. Menor carga absoluta
    3. Mayor capacidad disponible
    4. asesor_id ASC (determinismo)
    """
    if not candidatos:
        return None

    return min(
        candidatos,
        key=lambda a: (
            a.carga_relativa,
            a.carga_diaria,
            -a.capacidad_disponible,
            a.asesor_id,
        ),
    )


def determinar_razon_sin_asignar(
    asesores_en_pv: List[Asesor],
    empresa_id: str,
    punto_venta_id: str,
) -> str:
    """
    Determina la razón por la que un lead no puede ser asignado.
    """
    compatibles = [
        a for a in asesores_en_pv
        if a.empresa_id == empresa_id and a.punto_venta_id == punto_venta_id
    ]

    if not compatibles:
        return RAZON_SIN_ASESOR_COMPATIBLE

    activos = [a for a in compatibles if a.activo]
    if not activos:
        return RAZON_SIN_ASESOR_ACTIVO

    # Hay activos pero sin capacidad
    return RAZON_SIN_CAPACIDAD


def simular_asignacion_leads(
    leads: List[Lead],
    asesores: List[Asesor],
    cargas_iniciales: Optional[Dict[str, int]] = None,
    leads_ya_asignados: Optional[set] = None,
) -> List[ResultadoAsignacion]:
    """
    Simula la asignación de leads a asesores siguiendo las reglas del MVP.

    Parámetros:
        leads: Lista de leads a asignar.
        asesores: Lista de asesores con sus datos de capacidad.
        cargas_iniciales: Dict asesor_id -> carga inicial del día (0 si None).
        leads_ya_asignados: Set de lead_ids que ya cuentan con asignación vigente.

    Retorna:
        Lista de ResultadoAsignacion con el resultado de cada lead.

    IMPORTANTE: No modifica PostgreSQL directamente.
    La carga se mantiene en memoria durante la simulación.
    """
    # Inicializar cargas en memoria (copia del estado de entrada)
    carga_memoria: Dict[str, int] = {}
    for asesor in asesores:
        inicial = (cargas_iniciales or {}).get(asesor.asesor_id, 0)
        carga_memoria[asesor.asesor_id] = inicial

    # Ordenar leads por prioridad antes de procesar
    leads_ordenados = ordenar_leads_por_prioridad(leads)

    resultados: List[ResultadoAsignacion] = []
    ya_asignados_set = leads_ya_asignados or set()

    for lead in leads_ordenados:
        # Si el lead ya cuenta con asignación activa vigente, no consume capacidad
        if lead.lead_id in ya_asignados_set:
            resultados.append(ResultadoAsignacion(
                lead_id=lead.lead_id,
                empresa_id=lead.empresa_id,
                punto_venta_id=lead.punto_venta_id,
                puntaje_prioridad=lead.puntaje_prioridad,
                puntaje_urgencia=lead.puntaje_urgencia,
                asesor_asignado=None,
                razon_sin_asignar=RAZON_YA_ASIGNADO,
                asignado=False,
            ))
            continue

        # Construir estado de asesores con carga actual de memoria
        estado_asesores = [
            Asesor(
                asesor_id=a.asesor_id,
                empresa_id=a.empresa_id,
                punto_venta_id=a.punto_venta_id,
                activo=a.activo,
                capacidad_diaria_leads=a.capacidad_diaria_leads,
                carga_diaria=carga_memoria[a.asesor_id],
            )
            for a in asesores
        ]

        # Filtrar candidatos elegibles para este lead
        candidatos = [
            a for a in estado_asesores
            if a.es_elegible(lead.empresa_id, lead.punto_venta_id)
        ]

        if candidatos:
            asesor_seleccionado = seleccionar_asesor_optimo(candidatos)
            # Actualizar carga en memoria
            carga_memoria[asesor_seleccionado.asesor_id] += 1
            resultados.append(ResultadoAsignacion(
                lead_id=lead.lead_id,
                empresa_id=lead.empresa_id,
                punto_venta_id=lead.punto_venta_id,
                puntaje_prioridad=lead.puntaje_prioridad,
                puntaje_urgencia=lead.puntaje_urgencia,
                asesor_asignado=asesor_seleccionado.asesor_id,
                razon_sin_asignar=None,
                asignado=True,
            ))
        else:
            razon = determinar_razon_sin_asignar(
                asesores_en_pv=estado_asesores,
                empresa_id=lead.empresa_id,
                punto_venta_id=lead.punto_venta_id,
            )
            resultados.append(ResultadoAsignacion(
                lead_id=lead.lead_id,
                empresa_id=lead.empresa_id,
                punto_venta_id=lead.punto_venta_id,
                puntaje_prioridad=lead.puntaje_prioridad,
                puntaje_urgencia=lead.puntaje_urgencia,
                asesor_asignado=None,
                razon_sin_asignar=razon,
                asignado=False,
            ))

    return resultados


def cargas_finales_de_simulacion(
    asesores: List[Asesor],
    resultados: List[ResultadoAsignacion],
    cargas_iniciales: Optional[Dict[str, int]] = None,
) -> Dict[str, int]:
    """
    Calcula las cargas finales de cada asesor luego de la simulación.
    Útil para reportes y verificación de capacidad.
    """
    cargas: Dict[str, int] = {
        a.asesor_id: (cargas_iniciales or {}).get(a.asesor_id, 0)
        for a in asesores
    }
    for r in resultados:
        if r.asignado and r.asesor_asignado:
            cargas[r.asesor_asignado] = cargas.get(r.asesor_asignado, 0) + 1
    return cargas


def persistir_asignaciones(
    conn,
    asignaciones: List[ResultadoAsignacion],
) -> int:
    """
    Persiste en PostgreSQL las asignaciones generadas por el motor.

    Garantías:
    - Solo inserta resultados con asignado = True.
    - Utiliza ON CONFLICT (lead_id) WHERE es_actual = true DO NOTHING
      para garantizar idempotencia estricta en base de datos.
    - Retorna el número de nuevas asignaciones efectivamente insertadas.
    """
    to_insert = [
        (r.lead_id, r.asesor_asignado)
        for r in asignaciones
        if r.asignado and r.asesor_asignado
    ]

    if not to_insert:
        return 0

    insertados = 0
    with conn.cursor() as cur:
        for lead_id, asesor_id in to_insert:
            cur.execute("""
                INSERT INTO core.asignaciones (
                    lead_id,
                    asesor_id,
                    asignado_en,
                    es_actual
                ) VALUES (%s, %s, CURRENT_TIMESTAMP, true)
                ON CONFLICT (lead_id) WHERE es_actual = true DO NOTHING;
            """, (lead_id, asesor_id))
            insertados += cur.rowcount

    return insertados
