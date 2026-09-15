"""
tests/test_scoring.py
---------------------
Pruebas unitarias e integradas para el scoring Híbrido (Logistic Regression V1 + Fallback Rules V1).
Contiene las validaciones obligatorias 1 a 10 de la Fase 9B.2.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import datetime, timedelta
import pytest
from database import get_connection
from services.scoring_service import (
    calcular_puntaje_prioridad,
    calcular_puntaje_logistico,
    evaluar_scoring_hibrido,
    determinar_temperatura,
    normalizar_booleano_cuota,
    normalizar_metodo_pago,
    evaluar_y_guardar_scoring_lead,
)


def test_1_lead_alta_prioridad():
    """
    Test 1: Lead con horas_espera < 1h, pidio_cita = SI, cuota = SI -> Score Alto/Crítico.
    """
    res_rules = calcular_puntaje_prioridad(horas=0.5, pidio_cita=True, manifesto_cuota_inicial=True)
    assert res_rules["puntaje_prioridad"] == 100.0
    assert res_rules["temperatura"] == "Crítico"

    res_lr = calcular_puntaje_logistico(horas=0.5, pidio_cita="SI", manifesto_cuota_inicial="SI", metodo_pago="contado")
    assert res_lr["puntaje_prioridad"] >= 70.0
    assert res_lr["temperatura"] in ("Alto", "Crítico")


def test_2_lead_baja_prioridad():
    """
    Test 2: Lead con horas_espera > 48h, pidio_cita = NO, cuota = NO -> Score Bajo.
    """
    res_rules = calcular_puntaje_prioridad(horas=50.0, pidio_cita=False, manifesto_cuota_inicial=False)
    assert res_rules["puntaje_prioridad"] == 7.0
    assert res_rules["temperatura"] == "Bajo"

    res_lr = calcular_puntaje_logistico(horas=50.0, pidio_cita="NO", manifesto_cuota_inicial="NO", metodo_pago="credito")
    assert res_lr["puntaje_prioridad"] <= 35.0
    assert res_lr["temperatura"] in ("Bajo", "Medio")


def test_3_fallback_por_variables_faltantes():
    """
    Test 3: Lead sin extracciones conversacionales -> Activa modelo Fallback Rules V1.
    """
    lead_data_sin_extraccion = {
        "solicita_cita": None,
        "pago_inicial": None,
        "metodo_pago": None,
    }
    res = evaluar_scoring_hibrido(lead_data_sin_extraccion, horas=2.0)
    assert res["modelo_scoring"] == "rules"
    assert res["version_scoring"] == "v1.0"


def test_4_forma_pago_desconocida():
    """
    Test 4: Forma de pago desconocida -> NO se interpreta automáticamente como contado.
    """
    es_credito, etiqueta = normalizar_metodo_pago(None)
    assert es_credito is None
    assert etiqueta == "NO_INFORMADO"

    es_credito2, etiqueta2 = normalizar_metodo_pago("DESCONOCIDO")
    assert es_credito2 is None
    assert etiqueta2 == "NO_INFORMADO"


def test_5_limites_score_0_a_100():
    """
    Test 5: El score siempre debe mantenerse acotado en [0, 100].
    """
    for h in [0.0, 0.1, 10.0, 50.0, 200.0]:
        for c in [True, False, None]:
            for q in [True, False, None]:
                res = calcular_puntaje_logistico(horas=h, pidio_cita=c, manifesto_cuota_inicial=q)
                assert 0.0 <= res["puntaje_prioridad"] <= 100.0


def test_6_consistencia_temperatura():
    """
    Test 6: Temperatura consistente con el puntaje de prioridad.
    - 0 - 24.99 : Bajo
    - 25 - 49.99 : Medio
    - 50 - 74.99 : Alto
    - 75 - 100   : Crítico
    """
    assert determinar_temperatura(10.0) == "Bajo"
    assert determinar_temperatura(35.0) == "Medio"
    assert determinar_temperatura(60.0) == "Alto"
    assert determinar_temperatura(85.0) == "Crítico"


def test_7_razones_coherentes():
    """
    Test 7: Razones explicables estructuradas e inteligibles.
    """
    res = calcular_puntaje_logistico(horas=0.5, pidio_cita="SI", manifesto_cuota_inicial="SI", metodo_pago="credito")
    razones = res["razones"]
    assert "modelo" in razones
    assert razones["modelo"] == "logistic_regression"
    assert "factores_clave" in razones
    assert isinstance(razones["factores_clave"], list)
    assert len(razones["factores_clave"]) > 0


def test_8_idempotencia_y_test_9_un_score_actual():
    """
    Tests 8 y 9: Re-scoring mantiene exactamente 1 registro con es_actual = TRUE por lead.
    """
    lead_id = "LEAD-001"
    with get_connection() as conn:
        res1 = evaluar_y_guardar_scoring_lead(conn, lead_id)
        assert res1["lead_id"] == lead_id

        res2 = evaluar_y_guardar_scoring_lead(conn, lead_id)
        assert res2["lead_id"] == lead_id

        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM core.puntajes_leads
                WHERE lead_id = %s AND es_actual = TRUE;
            """, (lead_id,))
            count_actual = cur.fetchone()[0]
            assert count_actual == 1, f"Se esperaba 1 registro es_actual = TRUE, se encontraron {count_actual}"


def test_10_compatibilidad_sinteticos():
    """
    Test 10: Los 7 leads sintéticos continúan puntuándose correctamente sin romper el sistema.
    """
    sinteticos = [f"LEAD-00{i}" for i in range(1, 8)]
    with get_connection() as conn:
        for sid in sinteticos:
            res = evaluar_y_guardar_scoring_lead(conn, sid)
            assert res["lead_id"] == sid
            assert 0.0 <= res["puntaje_prioridad"] <= 100.0


# Funciones de test heredadas para compatibilidad con suites anteriores
def test_validacion_1_menos_1h_sin_cita_sin_cuota():
    res = calcular_puntaje_prioridad(horas=0.5, pidio_cita=False, manifesto_cuota_inicial=False)
    assert res["puntaje_prioridad"] == 70.0
    assert res["temperatura"] == "Alto"


def test_validacion_2_entre_4_12h_con_cita_con_cuota():
    res = calcular_puntaje_prioridad(horas=6.2, pidio_cita=True, manifesto_cuota_inicial=True)
    assert res["puntaje_prioridad"] == 72.0
    assert res["temperatura"] == "Alto"


def test_validacion_3_mas_48h_sin_cita_sin_cuota():
    res = calcular_puntaje_prioridad(horas=50.0, pidio_cita=False, manifesto_cuota_inicial=False)
    assert res["puntaje_prioridad"] == 7.0
    assert res["temperatura"] == "Bajo"


def test_validacion_4_menos_1h_con_cita_con_cuota():
    res = calcular_puntaje_prioridad(horas=0.2, pidio_cita=True, manifesto_cuota_inicial=True)
    assert res["puntaje_prioridad"] == 100.0
    assert res["temperatura"] == "Crítico"


def test_validacion_5_limites_score():
    res1 = calcular_puntaje_prioridad(horas=100.0, pidio_cita=False, manifesto_cuota_inicial=False)
    assert 0.0 <= res1["puntaje_prioridad"] <= 100.0


def test_validacion_6_no_informa_cuota():
    assert normalizar_booleano_cuota("NO_INFORMA") is False
    assert normalizar_booleano_cuota("NO") is False
    assert normalizar_booleano_cuota(None) is False


if __name__ == "__main__":
    test_1_lead_alta_prioridad()
    test_2_lead_baja_prioridad()
    test_3_fallback_por_variables_faltantes()
    test_4_forma_pago_desconocida()
    test_5_limites_score_0_a_100()
    test_6_consistencia_temperatura()
    test_7_razones_coherentes()
    test_8_idempotencia_y_test_9_un_score_actual()
    test_10_compatibilidad_sinteticos()
    test_validacion_1_menos_1h_sin_cita_sin_cuota()
    test_validacion_2_entre_4_12h_con_cita_con_cuota()
    test_validacion_3_mas_48h_sin_cita_sin_cuota()
    test_validacion_4_menos_1h_con_cita_con_cuota()
    test_validacion_5_limites_score()
    test_validacion_6_no_informa_cuota()
    print("ALL TESTS PASSED SUCCESSFULLY!")
