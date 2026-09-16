"""
tests/test_conversation_engine.py
----------------------------------
Suite de pruebas unitarias y de integración para el Motor Conversacional Guiado (Fase 9G.3).
Cubre los 14 escenarios obligatorios + pruebas End-to-End y de atajo.
"""

import pytest
from services.conversation_engine import (
    EstadoConversacional,
    process_turn,
    resolver_siguiente_variable,
    DESCONOCIDO,
    CONOCIDO,
    CONFIRMADO,
    AMBIGUO,
    CAMBIADO,
    NO_APLICA,
    PREG_SELECCIONAR_MODELO,
    PREG_CONFIRMAR_METODO_PAGO,
    PREG_SOLICITAR_PAGO_INICIAL,
    PREG_SOLICITAR_COTIZACION,
    PREG_CONFIRMAR_CITA,
    PREG_SOLICITAR_SEDE,
    PREG_NINGUNA,
    VAR_MODELO,
    VAR_PAGO,
    VAR_INICIAL,
    VAR_COTIZACION,
    VAR_CITA,
    VAR_SEDE,
    VAR_FINALIZADO,
)

# Catálogo simulado para pruebas
CATALOGO_MOCK = [
    {
        "sku": "SKU-010",
        "marca": "Bajaj",
        "linea": "Pulsar RS 200",
        "cilindraje_cc": 199,
        "segmento": "Deportiva",
        "precio_lista": 16500000,
    },
    {
        "sku": "SKU-005",
        "marca": "TVS",
        "linea": "Apache RTR 160",
        "cilindraje_cc": 159,
        "segmento": "Calle",
        "precio_lista": 9800000,
    },
    {
        "sku": "SKU-012",
        "marca": "Bajaj",
        "linea": "Dominar 400",
        "cilindraje_cc": 373,
        "segmento": "Touring",
        "precio_lista": 18900000,
    },
]


def test_inicio_sin_modelo():
    messages = [{"role": "user", "content": "Hola, quiero una moto."}]
    bot_text, estado = process_turn(messages, CATALOGO_MOCK)
    assert estado.pregunta_pendiente == PREG_SELECCIONAR_MODELO
    assert estado.estado_modelo == DESCONOCIDO
    assert "modelo" in bot_text.lower()


def test_modelo_especificado():
    messages = [{"role": "user", "content": "Una Pulsar RS 200."}]
    bot_text, estado = process_turn(messages, CATALOGO_MOCK)
    assert estado.modelo_interes == "SKU-010"
    assert estado.estado_modelo == CONOCIDO
    assert estado.pregunta_pendiente == PREG_CONFIRMAR_METODO_PAGO
    assert "16.500.000" in bot_text or "contado o mediante financiación" in bot_text.lower()


def test_pago_contado():
    messages = [
        {"role": "user", "content": "Quiero la Pulsar RS 200"},
        {"role": "user", "content": "voy a pagar todo"},
    ]
    bot_text, estado = process_turn(messages, CATALOGO_MOCK)
    assert estado.metodo_pago == "Contado"
    assert estado.estado_inicial == NO_APLICA
    assert estado.pago_inicial is None
    assert estado.pregunta_pendiente == PREG_SOLICITAR_COTIZACION or estado.pregunta_pendiente == PREG_CONFIRMAR_CITA


def test_pago_credito():
    messages = [
        {"role": "user", "content": "Pulsar RS 200"},
        {"role": "user", "content": "quiero financiarla"},
    ]
    bot_text, estado = process_turn(messages, CATALOGO_MOCK)
    assert estado.metodo_pago == "Crédito"
    assert estado.pregunta_pendiente == PREG_SOLICITAR_PAGO_INICIAL
    assert "cuota inicial" in bot_text.lower()


def test_credito_con_inicial_simultaneo():
    messages = [
        {"role": "user", "content": "Pulsar RS 200"},
        {"role": "user", "content": "Quiero financiarla y tengo 3 millones para la inicial."},
    ]
    bot_text, estado = process_turn(messages, CATALOGO_MOCK)
    assert estado.metodo_pago == "Crédito"
    assert estado.pago_inicial == 3000000
    assert estado.pregunta_pendiente == PREG_SOLICITAR_COTIZACION
    assert "3.000.000" in bot_text


def test_precio_contextual():
    # Turno 1: Modelo
    messages = [{"role": "user", "content": "Pulsar RS 200"}]
    _, estado = process_turn(messages, CATALOGO_MOCK)
    
    # Turno 2: ¿Cuánto vale?
    messages.append({"role": "bot", "content": "..."})
    messages.append({"role": "user", "content": "¿Cuánto vale?"})
    bot_text, estado = process_turn(messages, CATALOGO_MOCK, estado_previo=estado)
    
    assert estado.modelo_interes == "SKU-010"
    assert "16.500.000" in bot_text or "cuánto" in bot_text.lower() or "pulsar" in bot_text.lower()
    assert "qué modelo" not in bot_text.lower()  # NO volvió a preguntar el modelo


def test_si_contextual_cita():
    estado = EstadoConversacional(
        modelo_interes="SKU-010",
        nombre_modelo="Pulsar RS 200",
        metodo_pago="Contado",
        solicita_cotizacion=True,
        pregunta_pendiente=PREG_CONFIRMAR_CITA
    )
    messages = [
        {"role": "user", "content": "Pulsar RS 200"},
        {"role": "bot", "content": "¿Te gustaría agendar una cita?"},
        {"role": "user", "content": "sí"}
    ]
    bot_text, estado = process_turn(messages, CATALOGO_MOCK, estado_previo=estado)
    assert estado.solicita_cita is True
    assert estado.pregunta_pendiente == PREG_SOLICITAR_SEDE
    assert "ciudad" in bot_text.lower() or "sede" in bot_text.lower()


def test_no_contextual_cita():
    estado = EstadoConversacional(
        modelo_interes="SKU-010",
        pregunta_pendiente=PREG_CONFIRMAR_CITA
    )
    messages = [
        {"role": "user", "content": "Pulsar RS 200"},
        {"role": "bot", "content": "¿Te gustaría agendar una cita?"},
        {"role": "user", "content": "por ahora no"}
    ]
    bot_text, estado = process_turn(messages, CATALOGO_MOCK, estado_previo=estado)
    assert estado.solicita_cita is False


def test_solicitar_sede():
    estado = EstadoConversacional(
        modelo_interes="SKU-010",
        metodo_pago="Contado",
        solicita_cotizacion=True,
        solicita_cita=True,
        pregunta_pendiente=PREG_SOLICITAR_SEDE
    )
    messages = [
        {"role": "user", "content": "Armenia"}
    ]
    bot_text, estado = process_turn(messages, CATALOGO_MOCK, estado_previo=estado)
    assert estado.ciudad_sede == "Armenia"
    assert estado.pregunta_pendiente == PREG_NINGUNA


def test_cambio_modelo():
    messages = [{"role": "user", "content": "Pulsar RS 200"}]
    _, estado = process_turn(messages, CATALOGO_MOCK)
    assert estado.modelo_interes == "SKU-010"

    messages.append({"role": "user", "content": "Mejor quiero la Apache RTR 160"})
    bot_text, estado = process_turn(messages, CATALOGO_MOCK, estado_previo=estado)
    assert estado.modelo_interes == "SKU-005"
    assert estado.estado_modelo == CAMBIADO
    assert "SKU-010" in estado.historial_modelos
    assert "Apache" in bot_text or "9.800.000" in bot_text


def test_ambiguedad_modelos():
    messages = [{"role": "user", "content": "Estoy entre la Pulsar o la Dominar"}]
    bot_text, estado = process_turn(messages, CATALOGO_MOCK)
    assert estado.estado_modelo == AMBIGUO
    assert "excelentes opciones" in bot_text.lower() or "cuál" in bot_text.lower()


def test_si_sin_contexto():
    estado = EstadoConversacional(pregunta_pendiente=PREG_NINGUNA)
    messages = [{"role": "user", "content": "sí"}]
    bot_text, estado = process_turn(messages, CATALOGO_MOCK, estado_previo=estado)
    assert "modelo" in bot_text.lower() or "ayudarte" in bot_text.lower()


def test_no_repetir_variable():
    estado = EstadoConversacional(modelo_interes="SKU-010", estado_modelo=CONOCIDO)
    messages = [{"role": "user", "content": "quiero cotizar"}]
    bot_text, estado = process_turn(messages, CATALOGO_MOCK, estado_previo=estado)
    assert "qué modelo" not in bot_text.lower()


def test_contado_no_solicita_inicial():
    estado = EstadoConversacional(
        modelo_interes="SKU-010",
        metodo_pago="Contado",
        estado_pago=CONOCIDO,
        estado_inicial=NO_APLICA
    )
    siguiente = resolver_siguiente_variable(estado)
    assert siguiente != VAR_INICIAL


def test_end_to_end_flow():
    # Turno 1: Inicio
    msgs = [{"role": "user", "content": "Hola, quiero una moto."}]
    res, st = process_turn(msgs, CATALOGO_MOCK)
    assert st.pregunta_pendiente == PREG_SELECCIONAR_MODELO

    # Turno 2: Modelo
    msgs.append({"role": "user", "content": "Pulsar RS 200."})
    res, st = process_turn(msgs, CATALOGO_MOCK, estado_previo=st)
    assert st.modelo_interes == "SKU-010"

    # Turno 3: Pago Crédito
    msgs.append({"role": "user", "content": "A crédito."})
    res, st = process_turn(msgs, CATALOGO_MOCK, estado_previo=st)
    assert st.metodo_pago == "Crédito"

    # Turno 4: Cuota Inicial
    msgs.append({"role": "user", "content": "3 millones."})
    res, st = process_turn(msgs, CATALOGO_MOCK, estado_previo=st)
    assert st.pago_inicial == 3000000

    # Turno 5: Cotización Sí
    msgs.append({"role": "user", "content": "Sí."})
    res, st = process_turn(msgs, CATALOGO_MOCK, estado_previo=st)
    assert st.solicita_cotizacion is True

    # Turno 6: Cita Sí
    msgs.append({"role": "user", "content": "Sí."})
    res, st = process_turn(msgs, CATALOGO_MOCK, estado_previo=st)
    assert st.solicita_cita is True

    # Turno 7: Sede Armenia
    msgs.append({"role": "user", "content": "Armenia."})
    res, st = process_turn(msgs, CATALOGO_MOCK, estado_previo=st)
    assert st.ciudad_sede == "Armenia"
    assert st.pregunta_pendiente == PREG_NINGUNA


def test_build_extraction_view_sincronizacion_completa():
    from services.conversation_engine import build_extraction_view
    
    msgs = [{"role": "user", "content": "hola"}]
    res, st = process_turn(msgs, CATALOGO_MOCK)
    
    msgs.append({"role": "user", "content": "Pulsar RS 200"})
    res, st = process_turn(msgs, CATALOGO_MOCK, estado_previo=st)

    msgs.append({"role": "user", "content": "CONTADO"})
    res, st = process_turn(msgs, CATALOGO_MOCK, estado_previo=st)

    msgs.append({"role": "user", "content": "SI"})
    res, st = process_turn(msgs, CATALOGO_MOCK, estado_previo=st)

    msgs.append({"role": "user", "content": "SI"})
    res, st = process_turn(msgs, CATALOGO_MOCK, estado_previo=st)

    msgs.append({"role": "user", "content": "Pereira"})
    res, st = process_turn(msgs, CATALOGO_MOCK, estado_previo=st)

    view = build_extraction_view(st)
    assert view["sku_motocicleta"] == "SKU-010"
    assert view["metodo_pago"] == "Contado"
    assert view["pago_inicial"] == "NO_APLICA"
    assert view["solicita_cotizacion"] is True
    assert view["solicita_cita"] is True
    assert view["ciudad_sede"] == "Pereira"
    assert view["intencion_declarada"] == "Compra"


def test_build_extraction_view_negacion():
    from services.conversation_engine import build_extraction_view
    st = EstadoConversacional(pregunta_pendiente=PREG_SOLICITAR_COTIZACION)
    msgs = [{"role": "user", "content": "No"}]
    res, st = process_turn(msgs, CATALOGO_MOCK, estado_previo=st)
    view = build_extraction_view(st)
    assert view["solicita_cotizacion"] is False


def test_build_extraction_view_independencia():
    from services.conversation_engine import build_extraction_view
    st = EstadoConversacional(solicita_cotizacion=True, solicita_cita=False)
    view = build_extraction_view(st)
    assert view["solicita_cotizacion"] is True
    assert view["solicita_cita"] is False


def test_build_extraction_view_reinicio():
    from services.conversation_engine import build_extraction_view
    st_limpio = EstadoConversacional()
    view = build_extraction_view(st_limpio)
    assert view["sku_motocicleta"] is None
    assert view["solicita_cotizacion"] is None
    assert view["solicita_cita"] is None

