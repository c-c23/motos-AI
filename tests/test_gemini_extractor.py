"""
tests/test_gemini_extractor.py
------------------------------
Suite de pruebas unitarias para el extractor semántico con Gemini y su mecanismo de fallback.
Todos los tests utilizan mocks y NO realizan llamadas a la API real de Gemini.
"""

import os
import json
import pytest
from unittest.mock import MagicMock, patch
from pydantic import ValidationError

from ai.schemas import AnalisisSemantico, ResultadoExtraccion
from ai.gemini_extractor import (
    extraer_analisis_semantico_gemini,
    analizar_conversacion,
    _crear_analisis_fallback,
)

CATALOGO_MOCK = [
    {
        "sku": "SKU-001",
        "marca": "Honda",
        "linea": "CB 125F Twister",
        "cilindraje_cc": 125,
        "segmento": "Calle",
        "precio_lista": 7500000,
    },
    {
        "sku": "SKU-010",
        "marca": "Bajaj",
        "linea": "Pulsar RS 200",
        "cilindraje_cc": 199,
        "segmento": "Deportiva",
        "precio_lista": 16500000,
    }
]


def test_gemini_respuesta_valida():
    """Test 1: Gemini devuelve respuesta JSON válida que pasa la validación Pydantic."""
    json_valido = json.dumps({
        "intencion_compra": "alta",
        "urgencia": "alta",
        "fase_embudo": "visita",
        "solicita_asesor": True,
        "solicita_cotizacion": False,
        "solicita_cita": True,
        "objecion_principal": None,
        "senales_compra": ["Tiene 4 palos para inicial", "Va en camino hoy"],
        "confianza": 0.95
    })

    mock_client = MagicMock()
    mock_interaction = MagicMock()
    mock_interaction.output_text = json_valido
    mock_client.interactions.create.return_value = mock_interaction

    resultado = extraer_analisis_semantico_gemini(
        mensajes="Financiada, tengo 4 palos",
        client=mock_client
    )

    assert isinstance(resultado, AnalisisSemantico)
    assert resultado.intencion_compra == "alta"
    assert resultado.urgencia == "alta"
    assert resultado.fase_embudo == "visita"
    assert resultado.solicita_cita is True
    assert resultado.confianza == 0.95
    assert len(resultado.senales_compra) == 2


def test_gemini_json_invalido_lanza_error():
    """Test 2: Gemini devuelve JSON malformado -> ValidationError o ValueError."""
    mock_client = MagicMock()
    mock_interaction = MagicMock()
    mock_interaction.output_text = "{ json roto: incompleto"
    mock_client.interactions.create.return_value = mock_interaction

    with pytest.raises((ValidationError, ValueError)):
        extraer_analisis_semantico_gemini(
            mensajes="Hola",
            client=mock_client
        )


def test_gemini_valores_invalidos_pydantic():
    """Test 3: Gemini devuelve valores fuera de los permitidos -> Pydantic lo rechaza."""
    json_invalido = json.dumps({
        "intencion_compra": "SUPER_ALTA",  # Valor no permitido por Literal
        "urgencia": "inmediata",           # Valor no permitido
        "fase_embudo": "decision",          # Valor no permitido
        "solicita_asesor": True,
        "solicita_cotizacion": False,
        "solicita_cita": True,
        "objecion_principal": None,
        "senales_compra": [],
        "confianza": 1.5                   # Fuera del rango 0.0 - 1.0
    })

    mock_client = MagicMock()
    mock_interaction = MagicMock()
    mock_interaction.output_text = json_invalido
    mock_client.interactions.create.return_value = mock_interaction

    with pytest.raises(ValidationError):
        extraer_analisis_semantico_gemini(
            mensajes="Hola",
            client=mock_client
        )


def test_gemini_lanza_excepcion_red():
    """Test 4: Gemini lanza excepción por timeout o fallo de conexión."""
    mock_client = MagicMock()
    mock_client.interactions.create.side_effect = TimeoutError("Connection timed out to Gemini API")

    with pytest.raises(TimeoutError):
        extraer_analisis_semantico_gemini(
            mensajes="Hola",
            client=mock_client
        )


def test_fallback_activado_por_excepcion():
    """Test 5: Al fallar Gemini, analizar_conversacion activa el extractor determinista como fallback."""
    mock_client = MagicMock()
    mock_client.interactions.create.side_effect = Exception("API rate limit exceeded")

    mensajes = [
        {"role": "user", "content": "Buenas, estoy interesado en una Pulsar RS 200 de contado, ¿me pueden agendar cita?"}
    ]

    resultado = analizar_conversacion(
        mensajes=mensajes,
        catalogo=CATALOGO_MOCK,
        client=mock_client
    )

    assert isinstance(resultado, ResultadoExtraccion)
    assert resultado.modelo_extraccion == "reglas"
    assert resultado.version_extraccion == "1.0"
    assert resultado.error_detalle is not None
    assert "API rate limit" in resultado.error_detalle

    # Validar que el fallback extrajo las variables por reglas
    assert resultado.sku_motocicleta == "SKU-010"
    assert resultado.metodo_pago == "Contado"
    assert resultado.analisis_semantico.solicita_cita is True
    assert resultado.analisis_semantico.intencion_compra == "alta"


def test_fallback_sin_api_key(monkeypatch):
    """Test 5b: Si no hay GEMINI_API_KEY en el entorno, activa el fallback sin caerse."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    mensajes = "Estoy averiguando por la Honda CB 125F Twister solo mirando precios"
    resultado = analizar_conversacion(
        mensajes=mensajes,
        catalogo=CATALOGO_MOCK,
        client=None
    )

    assert resultado.modelo_extraccion == "reglas"
    assert resultado.version_extraccion == "1.0"
    assert "GEMINI_API_KEY no configurada" in (resultado.error_detalle or "")
    assert resultado.sku_motocicleta == "SKU-001"


def test_caso_1_alta_intencion_urgencia():
    """Test 6: Caso 1 (Alta intención / Urgencia) validado con Mock."""
    caso_1_texto = (
        "Financiada, tengo 4 palos para la inicial.\n"
        "Claro, tengo contrato indefinido.\n"
        "¿A qué hora los puedo visitar hoy?\n"
        "Claro que sí, lo esperamos. Estamos de 8 a 6, ¿le separo la moto mientras tanto?\n"
        "Hágale pues, ya voy en camino"
    )

    json_simulado = json.dumps({
        "intencion_compra": "alta",
        "urgencia": "alta",
        "fase_embudo": "visita",
        "solicita_asesor": True,
        "solicita_cotizacion": False,
        "solicita_cita": True,
        "objecion_principal": None,
        "senales_compra": [
            "Tiene 4 palos para cuota inicial",
            "Contrato indefinido",
            "Pregunta horario de visita para hoy",
            "Acepta separar la moto",
            "Va en camino"
        ],
        "confianza": 0.98
    })

    mock_client = MagicMock()
    mock_interaction = MagicMock()
    mock_interaction.output_text = json_simulado
    mock_client.interactions.create.return_value = mock_interaction

    resultado = analizar_conversacion(
        mensajes=caso_1_texto,
        catalogo=CATALOGO_MOCK,
        client=mock_client
    )

    assert resultado.modelo_extraccion == "gemini"
    assert resultado.analisis_semantico.intencion_compra == "alta"
    assert resultado.analisis_semantico.urgencia == "alta"
    assert resultado.analisis_semantico.fase_embudo == "visita"
    assert resultado.analisis_semantico.solicita_cita is True
    assert resultado.metodo_pago == "Crédito"
    assert resultado.pago_inicial == 4000000


def test_caso_2_interes_objecion_financiera():
    """Test 7: Caso 2 (Interés + Objeción de intereses) validado con Mock."""
    caso_2_texto = (
        "A crédito, ¿cómo es el proceso?\n"
        "¿Y cuánto queda la cuota mensual? porque el interés está caro\n"
        "Le entiendo. ¿Le mando la cotización formal al WhatsApp para que la revise con calma?\n"
        "Sí porfa, mándemela"
    )

    json_simulado = json.dumps({
        "intencion_compra": "media",
        "urgencia": "media",
        "fase_embudo": "cotizacion",
        "solicita_asesor": False,
        "solicita_cotizacion": True,
        "solicita_cita": False,
        "objecion_principal": "Tasa de interés elevada / interés caro",
        "senales_compra": [
            "Pregunta por proceso de crédito",
            "Pregunta valor de cuota mensual",
            "Acepta envío de cotización formal"
        ],
        "confianza": 0.92
    })

    mock_client = MagicMock()
    mock_interaction = MagicMock()
    mock_interaction.output_text = json_simulado
    mock_client.interactions.create.return_value = mock_interaction

    resultado = analizar_conversacion(
        mensajes=caso_2_texto,
        catalogo=CATALOGO_MOCK,
        client=mock_client
    )

    assert resultado.modelo_extraccion == "gemini"
    assert resultado.analisis_semantico.intencion_compra == "media"
    assert resultado.analisis_semantico.fase_embudo == "cotizacion"
    assert resultado.analisis_semantico.solicita_cotizacion is True
    assert resultado.analisis_semantico.objecion_principal is not None
    assert "interés" in resultado.analisis_semantico.objecion_principal.lower()
    assert resultado.metodo_pago == "Crédito"


def test_caso_3_exploracion():
    """Test 8: Caso 3 (Exploración / Mirando precios) validado con Mock."""
    caso_3_texto = (
        "Buenas, estoy averiguando por la Honda CB 125F Twister\n"
        "Solo estaba mirando precios"
    )

    json_simulado = json.dumps({
        "intencion_compra": "baja",
        "urgencia": "baja",
        "fase_embudo": "exploracion",
        "solicita_asesor": False,
        "solicita_cotizacion": False,
        "solicita_cita": False,
        "objecion_principal": None,
        "senales_compra": [],
        "confianza": 0.88
    })

    mock_client = MagicMock()
    mock_interaction = MagicMock()
    mock_interaction.output_text = json_simulado
    mock_client.interactions.create.return_value = mock_interaction

    resultado = analizar_conversacion(
        mensajes=caso_3_texto,
        catalogo=CATALOGO_MOCK,
        client=mock_client
    )

    assert resultado.modelo_extraccion == "gemini"
    assert resultado.analisis_semantico.intencion_compra == "baja"
    assert resultado.analisis_semantico.fase_embudo == "exploracion"
    assert resultado.analisis_semantico.urgencia in ("baja", "indeterminada")
    assert resultado.sku_motocicleta == "SKU-001"


def test_gemini_http_429_quota_fallback_inmediato():
    """Test 9: Error HTTP 429 de cuota en Gemini activa fallback inmediato a reglas con detalle de error."""
    mock_client = MagicMock()
    mock_client.interactions.create.side_effect = Exception(
        "Error code: 429 - {'error': {'message': 'Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20'}}"
    )

    mensajes = [{"role": "user", "content": "Hola, cuánto vale la Honda CB 125F Twister?"}]
    resultado = analizar_conversacion(
        mensajes=mensajes,
        catalogo=CATALOGO_MOCK,
        client=mock_client
    )

    assert resultado.modelo_extraccion == "reglas"
    assert resultado.version_extraccion == "1.0"
    assert "429" in resultado.error_detalle
    assert resultado.sku_motocicleta == "SKU-001"
    assert resultado.analisis_semantico.confianza == 0.5

