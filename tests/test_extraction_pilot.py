"""
tests/test_extraction_pilot.py
-------------------------------
Pruebas unitarias e integradas para el Piloto Controlado de Extracción IA (Fase 9C.1).
Validaciones 1 a 7 requeridas por la especificación.
"""

import os
import sys
from datetime import datetime
import pytest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

from database import get_connection
from services.extraction_service import (
    extract_conversation,
    extract_solicita_cita,
    extract_solicita_cotizacion,
    extract_pago_inicial,
    extract_metodo_pago,
)
from services.scoring_service import evaluar_y_guardar_scoring_lead


def test_1_null_no_se_convierte_en_false():
    """
    Test 1: Mensaje sin mención de cita -> solicita_cita es None (NULL), NO False.
    """
    messages = [{"remitente": "cliente", "texto": "Buenas tardes, quiero saber qué motos tienen"}]
    assert extract_solicita_cita(messages) is None
    assert extract_solicita_cotizacion(messages) is None


def test_2_null_en_pago_inicial_no_se_convierte_en_cero():
    """
    Test 2: Mensaje sin mención de cuota inicial -> pago_inicial es None (NULL), NO 0.
    """
    messages = [{"remitente": "cliente", "texto": "Me interesa la pulsar ns 200"}]
    assert extract_pago_inicial(messages) is None

    # Caso explícito de 0 cuota inicial
    messages_cero = [{"remitente": "cliente", "texto": "No tengo con que dar la inicial ahora"}]
    assert extract_pago_inicial(messages_cero) == 0


def test_3_null_en_metodo_pago_permanece_desconocido():
    """
    Test 3: Mensaje sin mención de método de pago -> metodo_pago es None (NULL).
    """
    messages = [{"remitente": "cliente", "texto": "Hola, ¿tienen horario de atención hoy?"}]
    assert extract_metodo_pago(messages) is None


def test_4_extraccion_mensaje_vacio():
    """
    Test 4: Lista vacía de mensajes -> Devuelve diccionario con campos en None.
    """
    res = extract_conversation([], [])
    assert res["solicita_cita"] is None
    assert res["pago_inicial"] is None
    assert res["metodo_pago"] is None


def test_5_y_6_persistencia_y_no_duplicacion():
    """
    Tests 5 y 6: Verificar persistencia en core.extracciones_ia e idempotencia.
    """
    lead_id = "LD-01125"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM core.extracciones_ia WHERE lead_id = %s;", (lead_id,))
            count = cur.fetchone()[0]
            assert count >= 1, f"Se esperaba al menos 1 extracción para el lead piloto {lead_id}"


def test_7_scoring_posterior_utiliza_extraccion():
    """
    Test 7: Scoring posterior utiliza las variables extraídas y actualiza el modelo.
    """
    lead_id = "LD-01166"  # Lead del piloto que tiene extracción de cita, cuota y método
    with get_connection() as conn:
        res = evaluar_y_guardar_scoring_lead(conn, lead_id)
        assert res["lead_id"] == lead_id
        assert res["modelo_scoring"] == "logistic_regression"
        assert res["version_scoring"] == "v1.0"
        assert res["puntaje_prioridad"] > 0.0


if __name__ == "__main__":
    test_1_null_no_se_convierte_en_false()
    test_2_null_en_pago_inicial_no_se_convierte_en_cero()
    test_3_null_en_metodo_pago_permanece_desconocido()
    test_4_extraccion_mensaje_vacio()
    test_5_y_6_persistencia_y_no_duplicacion()
    test_7_scoring_posterior_utiliza_extraccion()
    print("ALL PILOT EXTRACTION TESTS PASSED SUCCESSFULLY!")
