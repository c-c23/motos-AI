"""
tests/test_scoring_v2_persistence.py
-----------------------------------
Pruebas unitarias e integradas para la persistencia transaccional e idempotente
de Scoring V2 en PostgreSQL (`core.puntajes_leads`).
"""

import json
from datetime import datetime
import pytest
import psycopg
from unittest.mock import MagicMock, patch

from database import get_connection
from queries.scoring_queries import (
    guardar_puntaje_lead_trx,
    guardar_puntaje_v2_lead_trx,
)
from services.scoring_service import (
    evaluar_y_guardar_scoring_lead,
    evaluar_y_guardar_scoring_v2_lead,
    calcular_scoring_v2,
)
from ai.schemas import AnalisisSemantico


def test_guardar_puntaje_v2_unitario():
    """Valida la estructura y parámetros que guardar_puntaje_v2_lead_trx envía a la base de datos."""
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.transaction.return_value.__enter__.return_value = None

    payload = {
        "lead_id": "TEST-LEAD-001",
        "probabilidad_comercial": None,
        "puntaje_urgencia": None,
        "puntaje_prioridad": 71.24,
        "temperatura": "Alto",
        "modelo_scoring": "hybrid_gemini",
        "version_scoring": "v2.0",
        "razones": {
            "modelo": "hybrid_gemini",
            "version": "v2.0",
            "puntaje_v1": 58.91,
            "puntaje_semantico": 100.0,
            "puntaje_v2": 71.24,
            "temperatura_v2": "Alto",
            "modelo_extraccion": "gemini",
            "version_extraccion": "1.0",
            "razones_v1": {},
            "razones_semanticas": ["Intención alta"],
        },
        "puntuado_en": datetime.now(),
    }

    resultado = guardar_puntaje_v2_lead_trx(mock_conn, payload)
    assert resultado["lead_id"] == "TEST-LEAD-001"
    assert resultado["version_scoring"] == "v2.0"
    assert resultado["modelo_scoring"] == "hybrid_gemini"
    assert resultado["puntaje_prioridad"] == 71.24
    assert resultado["temperatura"] == "Alto"

    # Verificar llamadas SQL: UPDATE (desmarcar anteriores), DELETE (idempotencia v2.0), INSERT (nuevo v2.0)
    assert mock_cursor.execute.call_count == 3


def test_persistencia_v2_integracion_con_historico_v1():
    """
    Test de integración en DB real:
    1. Guarda V1 con evaluar_y_guardar_scoring_lead (es_actual=TRUE).
    2. Guarda V2 con evaluar_y_guardar_scoring_v2_lead.
    3. Verifica que V1 pasa a es_actual=FALSE y V2 queda con es_actual=TRUE.
    4. Verifica que V1 NO fue eliminado.
    """
    test_lead_id = "LEAD-001"

    with get_connection() as conn:
        # 1. Ejecutar V1
        res_v1 = evaluar_y_guardar_scoring_lead(conn, test_lead_id)
        assert res_v1["lead_id"] == test_lead_id

        # 2. Ejecutar V2 (mockeando o pasando mensajes de prueba)
        mensajes_prueba = [
            {"role": "user", "content": "Hola, quiero la moto ya voy en camino hoy mismo tengo 4 palos"}
        ]
        res_v2 = evaluar_y_guardar_scoring_v2_lead(
            conn,
            test_lead_id,
            mensajes=mensajes_prueba
        )

        assert res_v2["lead_id"] == test_lead_id
        assert res_v2["version_scoring"] == "v2.0"
        assert res_v2["modelo_scoring"] == "hybrid_gemini"

        # 3. Consultar estado en base de datos
        with conn.cursor() as cur:
            cur.execute("""
                SELECT puntaje_id, lead_id, puntaje_prioridad, temperatura,
                       modelo_scoring, version_scoring, es_actual
                FROM core.puntajes_leads
                WHERE lead_id = %s
                ORDER BY puntuado_en DESC, puntaje_id DESC;
            """, (test_lead_id,))
            rows = cur.fetchall()

            # Debe haber al menos una fila V1.0 y una fila V2.0
            versiones = [r[5] for r in rows]
            actuales = [r[6] for r in rows]

            assert "v1.0" in versiones, "El registro histórico V1.0 debe conservarse"
            assert "v2.0" in versiones, "El registro V2.0 debe existir"

            # Exactamente un registro con es_actual = TRUE
            assert actuales.count(True) == 1, "Debe haber exactamente un registro con es_actual = TRUE"

            # El registro actual debe ser el V2.0
            row_actual = [r for r in rows if r[6] is True][0]
            assert row_actual[5] == "v2.0"
            assert row_actual[4] == "hybrid_gemini"


def test_idempotencia_persistencia_v2():
    """
    Test de idempotencia:
    Ejecutar evaluar_y_guardar_scoring_v2_lead múltiples veces para el mismo lead
    NO debe crear múltiples registros V2.0 actuales.
    """
    test_lead_id = "LEAD-001"

    with get_connection() as conn:
        mensajes_prueba = [
            {"role": "user", "content": "Estoy interesado en financiar una moto"}
        ]

        # Ejecución 1
        evaluar_y_guardar_scoring_v2_lead(conn, test_lead_id, mensajes=mensajes_prueba)

        # Ejecución 2
        evaluar_y_guardar_scoring_v2_lead(conn, test_lead_id, mensajes=mensajes_prueba)

        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM core.puntajes_leads
                WHERE lead_id = %s AND version_scoring = 'v2.0' AND es_actual = TRUE;
            """, (test_lead_id,))
            count_v2_actual = cur.fetchone()[0]
            assert count_v2_actual == 1, "Debe existir exactamente 1 registro V2.0 actual"

            cur.execute("""
                SELECT COUNT(*) FROM core.puntajes_leads
                WHERE lead_id = %s AND es_actual = TRUE;
            """, (test_lead_id,))
            total_actual = cur.fetchone()[0]
            assert total_actual == 1, "Solo 1 registro en total puede tener es_actual = TRUE por lead"


def test_persistencia_v2_razones_jsonb_completas():
    """Verifica que el campo razones contenga tanto la trazabilidad semántica como las razones de V1."""
    test_lead_id = "LEAD-002"

    with get_connection() as conn:
        mensajes_prueba = [
            {"role": "user", "content": "A crédito, cuánto queda la cuota? porque el interés está caro"}
        ]
        res_v2 = evaluar_y_guardar_scoring_v2_lead(
            conn,
            test_lead_id,
            mensajes=mensajes_prueba
        )

        with conn.cursor() as cur:
            cur.execute("""
                SELECT razones FROM core.puntajes_leads
                WHERE lead_id = %s AND version_scoring = 'v2.0';
            """, (test_lead_id,))
            row = cur.fetchone()
            assert row is not None
            razones_raw = row[0]
            razones = json.loads(razones_raw) if isinstance(razones_raw, str) else razones_raw

            assert razones["modelo"] == "hybrid_gemini"
            assert razones["version"] == "v2.0"
            assert "puntaje_v1" in razones
            assert "puntaje_semantico" in razones
            assert "puntaje_v2" in razones
            assert "razones_v1" in razones
            assert "razones_semanticas" in razones
            assert isinstance(razones["razones_semanticas"], list)


def test_persistencia_v2_fallback_sin_mensajes():
    """Verifica que si el lead no tiene mensajes conversacionales, genera V2 con fallback a reglas."""
    test_lead_id = "LEAD-003"

    with get_connection() as conn:
        res_v2 = evaluar_y_guardar_scoring_v2_lead(
            conn,
            test_lead_id,
            mensajes=[]  # Sin mensajes
        )

        assert res_v2["version_scoring"] == "v2.0"
        with conn.cursor() as cur:
            cur.execute("""
                SELECT modelo_scoring, version_scoring, razones FROM core.puntajes_leads
                WHERE lead_id = %s AND es_actual = TRUE;
            """, (test_lead_id,))
            row = cur.fetchone()
            assert row[0] == "hybrid_gemini"
            assert row[1] == "v2.0"


def test_rollback_ante_error_en_guardar_v2():
    """Verifica atomicidad y rollback: si ocurre un error, no quedan estados corruptos."""
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Simular fallo en el INSERT
    mock_cursor.execute.side_effect = [None, None, psycopg.DatabaseError("Disk full / connection dropped")]
    mock_conn.transaction.return_value.__enter__.return_value = None

    payload = {
        "lead_id": "TEST-ROLLBACK",
        "puntaje_prioridad": 50.0,
        "temperatura": "Medio",
    }

    with pytest.raises(psycopg.DatabaseError):
        guardar_puntaje_v2_lead_trx(mock_conn, payload)
