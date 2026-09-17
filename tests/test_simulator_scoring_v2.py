"""
tests/test_simulator_scoring_v2.py
----------------------------------
Suite de pruebas para la integración de Scoring V2 en el flujo de persistencia
del simulador conversacional (`services/persistence_service.py`).

Cubre los 6 casos exigidos:
1. Conversación normal: lead nuevo -> V1 -> V2 -> V2 actual.
2. Gemini disponible: modelo_extraccion=gemini, modelo_scoring=hybrid_gemini, v2.0.
3. Gemini falla / HTTP 429: fallback reglas, modelo_scoring=hybrid_gemini, v2.0, es_actual=true.
4. V1 histórico: V1.es_actual=false, V2.es_actual=true (ambos existen).
5. No duplicación: exactamente una sola fila activa (es_actual=true) por lead.
6. Rollback / Resiliencia: si falla V2, manejo seguro sin dejar transacciones rotas.
"""

import json
from unittest.mock import MagicMock, patch
import pytest
import psycopg

from database import get_connection
from services.persistence_service import guardar_conversacion_simulada
from ai.schemas import AnalisisSemantico


CATALOGO_TEST = [
    {
        "sku": "SKU-005",
        "marca": "TVS",
        "linea": "Apache RTR 160",
        "cilindraje_cc": 159,
        "segmento": "Calle",
        "precio_lista": 9800000,
    }
]

MENSAJES_TEST = [
    {"role": "user", "content": "Estoy interesado en la Apache RTR 160. Tengo 3 millones para la inicial y quiero comprarla. ¿Puedo ir hoy?"},
    {"role": "assistant", "content": "¡Excelente! La Apache RTR 160 es ideal. ¿Prefieres crédito o contado?"},
    {"role": "user", "content": "Financiación a crédito, cotización sí, cita sí en Pereira."},
]


def test_caso1_conversacion_normal():
    """
    Caso 1: Conversación normal
    Guarda lead nuevo, calcula V1 (histórico) y promueve a V2 (actual).
    """
    res = guardar_conversacion_simulada(
        messages=MENSAJES_TEST,
        catalogo=CATALOGO_TEST,
        nombre_cliente="Cliente Test Normal",
        empresa_id="EMP-01",
        punto_venta_id="PV-002",
    )

    assert "lead_id" in res
    assert "conversacion_id" in res
    assert "scoring" in res
    assert res["scoring"]["version_scoring"] == "v2.0"
    assert res["scoring"]["modelo_scoring"] == "hybrid_gemini"
    assert "scoring_v1" in res
    assert res["scoring_v1"]["version_scoring"] == "v1.0"


def test_caso2_gemini_disponible():
    """
    Caso 2: Gemini disponible
    Produce modelo_extraccion=gemini, modelo_scoring=hybrid_gemini, version_scoring=v2.0.
    """
    mock_sem = AnalisisSemantico(
        intencion_compra="alta",
        urgencia="alta",
        fase_embudo="compra",
        solicita_asesor=True,
        solicita_cotizacion=True,
        solicita_cita=True,
        senales_compra=["Tiene 3 millones", "Quiere ir hoy"],
        confianza=0.95,
    )

    with patch("ai.gemini_extractor.extraer_analisis_semantico_gemini", return_value=mock_sem):
        res = guardar_conversacion_simulada(
            messages=MENSAJES_TEST,
            catalogo=CATALOGO_TEST,
            nombre_cliente="Cliente Test Gemini OK",
        )

        sc = res["scoring"]
        assert sc["modelo_scoring"] == "hybrid_gemini"
        assert sc["version_scoring"] == "v2.0"
        razones = sc.get("razones", {})
        if isinstance(razones, str):
            razones = json.loads(razones)
        assert razones.get("modelo_extraccion") == "gemini"


def test_caso3_gemini_falla_o_429():
    """
    Caso 3: Gemini falla / HTTP 429
    Produce fallback con modelo_extraccion=reglas, pero scoring V2 (hybrid_gemini, v2.0, es_actual=true).
    """
    with patch(
        "ai.gemini_extractor.extraer_analisis_semantico_gemini",
        side_effect=RuntimeError("RESOURCE_EXHAUSTED 429 Quota exceeded"),
    ):
        res = guardar_conversacion_simulada(
            messages=MENSAJES_TEST,
            catalogo=CATALOGO_TEST,
            nombre_cliente="Cliente Test Gemini 429",
        )

        sc = res["scoring"]
        assert sc["modelo_scoring"] == "hybrid_gemini"
        assert sc["version_scoring"] == "v2.0"
        razones = sc.get("razones", {})
        if isinstance(razones, str):
            razones = json.loads(razones)
        assert razones.get("modelo_extraccion") == "reglas"


def test_caso4_v1_historico():
    """
    Caso 4: V1 histórico
    Después de V2:
    - V1.es_actual = false
    - V2.es_actual = true
    - V1 se conserva físicamente en core.puntajes_leads.
    """
    res = guardar_conversacion_simulada(
        messages=MENSAJES_TEST,
        catalogo=CATALOGO_TEST,
        nombre_cliente="Cliente Test Historico",
    )
    lead_id = res["lead_id"]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT version_scoring, modelo_scoring, es_actual, puntaje_prioridad
                FROM core.puntajes_leads
                WHERE lead_id = %s
                ORDER BY puntuado_en DESC, puntaje_id DESC;
            """, (lead_id,))
            rows = cur.fetchall()

            # Deben existir al menos v1.0 y v2.0
            versiones = {r[0]: (r[1], r[2]) for r in rows}
            assert "v1.0" in versiones, "V1 debe existir en base de datos"
            assert "v2.0" in versiones, "V2 debe existir en base de datos"

            # V1 debe ser histórico (es_actual=False)
            assert versiones["v1.0"][1] is False, "V1 debe quedar como es_actual = FALSE"

            # V2 debe ser el actual (es_actual=True)
            assert versiones["v2.0"][1] is True, "V2 debe quedar como es_actual = TRUE"


def test_caso5_no_duplicacion():
    """
    Caso 5: No duplicación
    Exactamente una sola fila con es_actual = true por lead en core.puntajes_leads.
    """
    res = guardar_conversacion_simulada(
        messages=MENSAJES_TEST,
        catalogo=CATALOGO_TEST,
        nombre_cliente="Cliente Test Unicidad",
    )
    lead_id = res["lead_id"]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*)
                FROM core.puntajes_leads
                WHERE lead_id = %s AND es_actual = TRUE;
            """, (lead_id,))
            count_actual = cur.fetchone()[0]
            assert count_actual == 1, "Debe haber exactamente 1 registro con es_actual = TRUE"


def test_caso6_resiliencia_error_v2():
    """
    Caso 6: Resiliencia / Rollback ante error en V2
    Si la función de Scoring V2 falla, guardar_conversacion_simulada no rompe
    la persistencia del lead y conserva el score V1 como fallback en res['scoring'].
    """
    with patch(
        "services.persistence_service.evaluar_y_guardar_scoring_v2_lead",
        side_effect=psycopg.DatabaseError("Error temporal de persistencia V2"),
    ):
        res = guardar_conversacion_simulada(
            messages=MENSAJES_TEST,
            catalogo=CATALOGO_TEST,
            nombre_cliente="Cliente Test Error V2",
        )

        assert "lead_id" in res
        assert "scoring_v2_error" in res
        # Debe haber conservado V1 en res['scoring'] como fallback
        assert res["scoring"]["version_scoring"] == "v1.0"
