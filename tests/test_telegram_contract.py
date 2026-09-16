from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from bot.telegram_bot import build_telegram_payload
from api.telegram import router, TelegramLeadRequest


@pytest.fixture
def api_client():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def test_1_payload_completo_no_pierde_variables():
    """
    Test 1 — Payload completo:
    Entrada:
      nombre = Cristian
      telefono = 3206693591
      motocicleta = Apache RTR 160
      metodo_pago = Crédito
      pago_inicial = 3000000
      solicita_cotizacion = True
      solicita_cita = True
    Debe verificarse que build_telegram_payload() no pierda ninguna de esas variables.
    """
    payload = build_telegram_payload(
        nombre="Cristian",
        telefono="3206693591",
        mensaje="Estoy interesado en una Apache RTR 160. Quiero crédito y tengo 3000000 de inicial.",
        motocicleta="Apache RTR 160",
        metodo_pago="Crédito",
        pago_inicial=3000000,
        solicita_cotizacion=True,
        solicita_cita=True,
        empresa_id="EMP-01",
        punto_venta_id="PV-001",
        telegram_user_id="test-123",
    )

    assert payload["telegram_user_id"] == "test-123"
    assert payload["nombre"] == "Cristian"
    assert payload["telefono"] == "3206693591"
    assert payload["mensaje"] == "Estoy interesado en una Apache RTR 160. Quiero crédito y tengo 3000000 de inicial."
    assert payload["motocicleta"] == "Apache RTR 160"
    assert payload["metodo_pago"] == "Crédito"
    assert payload["pago_inicial"] == 3000000
    assert payload["solicita_cotizacion"] is True
    assert payload["solicita_cita"] is True
    assert payload["empresa_id"] == "EMP-01"
    assert payload["punto_venta_id"] == "PV-001"


def test_2_api_recibe_payload_completo(api_client):
    """
    Test 2 — API recibe payload completo:
    Enviar el payload comercial completo a /api/v1/leads/telegram
    y verificar que el endpoint acepte el contrato.
    """
    payload = {
        "telegram_user_id": "test-123",
        "nombre": "Cristian",
        "telefono": "3206693591",
        "mensaje": "Estoy interesado en una Apache RTR 160. Quiero crédito y tengo 3000000 de inicial.",
        "motocicleta": "Apache RTR 160",
        "metodo_pago": "Crédito",
        "pago_inicial": 3000000,
        "solicita_cotizacion": True,
        "solicita_cita": True,
        "empresa_id": "EMP-01",
        "punto_venta_id": "PV-001",
    }

    response = api_client.post("/api/v1/leads/telegram", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["estado"] == "procesado"
    assert "lead_id" in data
    assert "conversacion_id" in data


def test_3_no_perdida_de_informacion_en_persistencia(api_client):
    """
    Test 3 — No pérdida de información:
    Mockear la persistencia y comprobar que extraccion_data y lead_data
    ya no contengan None / False cuando el payload sí contiene los valores comerciales.
    """
    payload = {
        "telegram_user_id": "test-456",
        "nombre": "Cristian",
        "telefono": "3206693591",
        "mensaje": "Quiero una Apache RTR 160 a crédito con 3 millones de inicial",
        "motocicleta": "Apache RTR 160",
        "metodo_pago": "Crédito",
        "pago_inicial": 3000000,
        "solicita_cotizacion": True,
        "solicita_cita": True,
        "empresa_id": "EMP-01",
        "punto_venta_id": "PV-001",
    }

    with patch("api.telegram.guardar_lead_completo_trx") as mock_guardar:
        mock_guardar.return_value = {
            "lead_id": "LD-TEST-001",
            "conversacion_id": "CONV-TEST-001",
        }

        response = api_client.post("/api/v1/leads/telegram", json=payload)
        assert response.status_code == 200
        assert mock_guardar.called

        kwargs = mock_guardar.call_args.kwargs
        lead_data = kwargs["lead_data"]
        extraccion_data = kwargs["extraccion_data"]

        # lead_data debe conservar el texto original y el SKU homologado
        assert lead_data["texto_modelo_original"] == "Apache RTR 160"
        assert lead_data["sku_motocicleta"] == "MOT-022"
        assert lead_data["empresa_id"] == "EMP-01"
        assert lead_data["punto_venta_id"] == "PV-001"

        # extraccion_data debe conservar la ficha completa sin descartar datos
        assert extraccion_data["sku_motocicleta"] == "MOT-022"
        assert extraccion_data["metodo_pago"] == "Crédito"
        assert extraccion_data["pago_inicial"] == 3000000
        assert extraccion_data["solicita_cotizacion"] is True
        assert extraccion_data["solicita_cita"] is True
        assert extraccion_data["intencion_declarada"] == "Compra"


def test_4_contado_sin_cuota_inicial_no_inventa_valor(api_client):
    """
    Test 4 — Contado:
    Verificar metodo_pago = Contado sin cuota inicial.
    No debe aparecer una cuota inventada.
    """
    payload = {
        "telegram_user_id": "test-contado",
        "nombre": "Ana Gomez",
        "telefono": "3109876543",
        "mensaje": "Quiero comprar de contado la Boxer CT 100",
        "motocicleta": "Boxer CT 100",
        "metodo_pago": "Contado",
        "pago_inicial": None,
        "solicita_cotizacion": True,
        "solicita_cita": False,
        "empresa_id": "EMP-01",
        "punto_venta_id": "PV-001",
    }

    with patch("api.telegram.guardar_lead_completo_trx") as mock_guardar:
        mock_guardar.return_value = {
            "lead_id": "LD-TEST-002",
            "conversacion_id": "CONV-TEST-002",
        }

        response = api_client.post("/api/v1/leads/telegram", json=payload)
        assert response.status_code == 200

        kwargs = mock_guardar.call_args.kwargs
        extraccion_data = kwargs["extraccion_data"]

        assert extraccion_data["metodo_pago"] == "Contado"
        assert extraccion_data["pago_inicial"] is None
        assert extraccion_data["solicita_cotizacion"] is True
        assert extraccion_data["solicita_cita"] is False


def test_5_credito_con_cuota_inicial(api_client):
    """
    Test 5 — Crédito:
    Verificar metodo_pago = Crédito y pago_inicial = 3000000.
    """
    payload = {
        "telegram_user_id": "test-credito",
        "nombre": "Carlos Lopez",
        "telefono": "3123456789",
        "mensaje": "Quiero financiar una Pulsar NS 160 y tengo 3000000 para la inicial",
        "motocicleta": "Pulsar NS 160",
        "metodo_pago": "Crédito",
        "pago_inicial": 3000000,
        "solicita_cotizacion": True,
        "solicita_cita": True,
        "empresa_id": "EMP-01",
        "punto_venta_id": "PV-001",
    }

    with patch("api.telegram.guardar_lead_completo_trx") as mock_guardar:
        mock_guardar.return_value = {
            "lead_id": "LD-TEST-003",
            "conversacion_id": "CONV-TEST-003",
        }

        response = api_client.post("/api/v1/leads/telegram", json=payload)
        assert response.status_code == 200

        kwargs = mock_guardar.call_args.kwargs
        extraccion_data = kwargs["extraccion_data"]

        assert extraccion_data["metodo_pago"] == "Crédito"
        assert extraccion_data["pago_inicial"] == 3000000
        assert extraccion_data["solicita_cotizacion"] is True
        assert extraccion_data["solicita_cita"] is True


def test_6_validacion_empresa_punto_venta_invalido(api_client):
    """
    Verifica que una combinación inválida de empresa_id y punto_venta_id
    genere error 400 Bad Request.
    """
    payload = {
        "telegram_user_id": "test-invalid-pv",
        "nombre": "Error Test",
        "telefono": "3001112233",
        "mensaje": "Mensaje de prueba",
        "empresa_id": "EMP-01",
        "punto_venta_id": "PV-999",  # No existe
    }

    response = api_client.post("/api/v1/leads/telegram", json=payload)
    assert response.status_code == 400
    assert "no es válida o está inactiva" in response.json()["detail"]
