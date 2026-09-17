"""
tests/test_scoring_v2.py
------------------------
Suite de pruebas para Scoring V2 (Scoring V1 + Señales Semánticas LLM).
Valida las 9 condiciones obligatorias de integración sin llamadas a la API real.
"""

import pytest
from unittest.mock import MagicMock
from ai.schemas import AnalisisSemantico
from services.scoring_service import (
    calcular_puntaje_prioridad,
    calcular_puntaje_logistico,
    calcular_puntaje_semantico,
    calcular_scoring_v2,
    determinar_temperatura,
)
from ai.gemini_extractor import analizar_conversacion


def test_1_v1_se_mantiene_funcionando():
    """Test 1: Scoring V1 (rules y logístico) continúa funcionando exactamente igual."""
    res_rules = calcular_puntaje_prioridad(horas=0.5, pidio_cita=True, manifesto_cuota_inicial=True)
    assert res_rules["puntaje_prioridad"] == 100.0
    assert res_rules["temperatura"] == "Crítico"
    assert res_rules["modelo_scoring"] == "rules"

    res_lr = calcular_puntaje_logistico(horas=0.5, pidio_cita="SI", manifesto_cuota_inicial="SI", metodo_pago="contado")
    assert res_lr["puntaje_prioridad"] >= 70.0
    assert res_lr["modelo_scoring"] == "logistic_regression"


def test_2_v2_combina_v1_y_semantica():
    """Test 2: V2 aplica exactamente la ponderación 70% V1 + 30% Semántico."""
    puntaje_v1 = 50.0
    analisis = AnalisisSemantico(
        intencion_compra="alta",       # 100 * 0.5 = 50
        urgencia="alta",               # 100 * 0.3 = 30
        fase_embudo="compra",          # 100 * 0.2 = 20 -> Base = 100
        solicita_asesor=False,
        solicita_cotizacion=False,
        solicita_cita=False,
        objecion_principal=None,
        senales_compra=["Va en camino"],
        confianza=0.95
    )
    # Semántico = 100.0
    # V2 = 0.70 * 50.0 + 0.30 * 100.0 = 35.0 + 30.0 = 65.0
    res_v2 = calcular_scoring_v2(puntaje_v1=puntaje_v1, analisis_semantico=analisis)
    assert res_v2["puntaje_v1"] == 50.0
    assert res_v2["puntaje_semantico"] == 100.0
    assert res_v2["puntaje_v2"] == 65.0
    assert res_v2["temperatura_v2"] == "Alto"


def test_3_intencion_alta_aumenta_componente_semantico():
    """Test 3: Intención alta produce mayor puntaje que intención media o baja."""
    analisis_alta = AnalisisSemantico(
        intencion_compra="alta",
        urgencia="indeterminada",
        fase_embudo="interes",
        solicita_asesor=False,
        solicita_cotizacion=False,
        solicita_cita=False,
        confianza=0.9
    )
    analisis_media = AnalisisSemantico(
        intencion_compra="media",
        urgencia="indeterminada",
        fase_embudo="interes",
        solicita_asesor=False,
        solicita_cotizacion=False,
        solicita_cita=False,
        confianza=0.9
    )
    analisis_baja = AnalisisSemantico(
        intencion_compra="baja",
        urgencia="indeterminada",
        fase_embudo="interes",
        solicita_asesor=False,
        solicita_cotizacion=False,
        solicita_cita=False,
        confianza=0.9
    )

    pts_alta, _ = calcular_puntaje_semantico(analisis_alta)
    pts_media, _ = calcular_puntaje_semantico(analisis_media)
    pts_baja, _ = calcular_puntaje_semantico(analisis_baja)

    assert pts_alta > pts_media > pts_baja
    assert pts_alta == (0.50 * 100 + 0.30 * 50 + 0.20 * 40)  # 50 + 15 + 8 = 73.0
    assert pts_media == (0.50 * 60 + 0.30 * 50 + 0.20 * 40)   # 30 + 15 + 8 = 53.0
    assert pts_baja == (0.50 * 20 + 0.30 * 50 + 0.20 * 40)    # 10 + 15 + 8 = 33.0


def test_4_urgencia_alta_aumenta_componente_semantico():
    """Test 4: Urgencia alta incrementa el puntaje semántico significativamente."""
    analisis_urg_alta = AnalisisSemantico(
        intencion_compra="media",
        urgencia="alta",
        fase_embudo="evaluacion",
        solicita_asesor=False,
        solicita_cotizacion=False,
        solicita_cita=False,
        confianza=0.9
    )
    analisis_urg_baja = AnalisisSemantico(
        intencion_compra="media",
        urgencia="baja",
        fase_embudo="evaluacion",
        solicita_asesor=False,
        solicita_cotizacion=False,
        solicita_cita=False,
        confianza=0.9
    )

    pts_alta, _ = calcular_puntaje_semantico(analisis_urg_alta)
    pts_baja, _ = calcular_puntaje_semantico(analisis_urg_baja)

    assert pts_alta > pts_baja
    assert pts_alta == (0.50 * 60 + 0.30 * 100 + 0.20 * 60)  # 30 + 30 + 12 = 72.0
    assert pts_baja == (0.50 * 60 + 0.30 * 20 + 0.20 * 60)   # 30 + 6 + 12 = 48.0


def test_5_confianza_baja_neutraliza_senales():
    """Test 5: Si confianza < 0.60, las señales semánticas se neutralizan a 50.0."""
    analisis_dudoso = AnalisisSemantico(
        intencion_compra="alta",
        urgencia="alta",
        fase_embudo="compra",
        solicita_asesor=True,
        solicita_cotizacion=True,
        solicita_cita=True,
        confianza=0.45  # < 0.60
    )

    pts_sem, razones = calcular_puntaje_semantico(analisis_dudoso)
    assert pts_sem == 50.0
    assert any("Confianza baja" in r for r in razones)

    # Con V1=40, V2 = 0.7*40 + 0.3*50 = 28 + 15 = 43.0
    res_v2 = calcular_scoring_v2(puntaje_v1=40.0, analisis_semantico=analisis_dudoso)
    assert res_v2["puntaje_semantico"] == 50.0
    assert res_v2["puntaje_v2"] == 43.0


def test_6_fallback_preserva_comportamiento():
    """Test 6: Cuando Gemini falla, se activa fallback y el scoring se mantiene consistente."""
    mock_client = MagicMock()
    mock_client.interactions.create.side_effect = RuntimeError("API Gemini no disponible")

    mensajes = [{"role": "user", "content": "Hola, sólo quiero información"}]
    res_ext = analizar_conversacion(mensajes, client=mock_client)
    assert res_ext.modelo_extraccion == "reglas"

    v1_dict = calcular_puntaje_prioridad(horas=10.0, pidio_cita=False, manifesto_cuota_inicial=False)
    res_v2 = calcular_scoring_v2(
        puntaje_v1=v1_dict,
        analisis_semantico=res_ext.analisis_semantico,
        modelo_extraccion="reglas"
    )
    assert res_v2["modelo_extraccion"] == "reglas"
    assert 0.0 <= res_v2["puntaje_v2"] <= 100.0


def test_7_limites_puntaje_v2_acotado_0_100():
    """Test 7: Puntaje V2 siempre acotado entre 0 y 100 inclusive."""
    analisis_max = AnalisisSemantico(
        intencion_compra="alta",
        urgencia="alta",
        fase_embudo="compra",
        solicita_asesor=True,
        solicita_cotizacion=True,
        solicita_cita=True,
        confianza=1.0
    )
    res_max = calcular_scoring_v2(puntaje_v1=100.0, analisis_semantico=analisis_max)
    assert res_max["puntaje_semantico"] == 100.0
    assert res_max["puntaje_v2"] == 100.0

    analisis_min = AnalisisSemantico(
        intencion_compra="baja",
        urgencia="baja",
        fase_embudo="exploracion",
        solicita_asesor=False,
        solicita_cotizacion=False,
        solicita_cita=False,
        confianza=1.0
    )
    res_min = calcular_scoring_v2(puntaje_v1=0.0, analisis_semantico=analisis_min)
    assert res_min["puntaje_semantico"] == 20.0
    assert res_min["puntaje_v2"] == 6.0


def test_8_razones_semanticas_se_conservan():
    """Test 8: Las razones semánticas y evidencias textuales se conservan en la salida."""
    analisis = AnalisisSemantico(
        intencion_compra="alta",
        urgencia="alta",
        fase_embudo="visita",
        solicita_asesor=True,
        solicita_cotizacion=False,
        solicita_cita=True,
        objecion_principal="Ninguna",
        senales_compra=["Tiene 4 palos para inicial", "Pregunta a qué hora visitar hoy"],
        confianza=0.95
    )

    res_v2 = calcular_scoring_v2(puntaje_v1=50.0, analisis_semantico=analisis)
    razones = res_v2["razones_semanticas"]

    assert any("Intención de compra: alta" in r for r in razones)
    assert any("Urgencia: alta" in r for r in razones)
    assert any("Solicita cita / visita" in r for r in razones)
    assert any("Tiene 4 palos para inicial" in r for r in razones)


def test_9_caso_ya_voy_en_camino_senales_relevantes():
    """Test 9: Caso 'ya voy en camino' genera señales semánticas de alto impacto."""
    analisis_caso1 = AnalisisSemantico(
        intencion_compra="alta",
        urgencia="alta",
        fase_embudo="compra",
        solicita_asesor=False,
        solicita_cotizacion=False,
        solicita_cita=True,
        senales_compra=[
            "Dispone de 4 millones para inicial",
            "Contrato a término indefinido",
            "Pregunta por horario para visitar hoy",
            "Confirma que ya va en camino"
        ],
        confianza=0.98
    )

    # Supongamos un lead con espera media (v1 = 42.0)
    res_v2 = calcular_scoring_v2(puntaje_v1=42.0, analisis_semantico=analisis_caso1)

    # Componente semántico alcanza el 100%
    assert res_v2["puntaje_semantico"] == 100.0
    # Puntaje V2 sube de 42.0 (Medio) a 59.4 (Alto)
    assert res_v2["puntaje_v2"] == 59.4
    assert res_v2["temperatura_v2"] == "Alto"
    assert len(res_v2["razones_semanticas"]) >= 5
