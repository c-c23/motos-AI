"""
services/conversation_engine.py
-------------------------------
Motor Conversacional Guiado con NLP, Estado y Variables Faltantes (Fase 9G.3).

Arquitectura desacoplada en 6 capas:
  1. Historial de Conversación
  2. Extractor NLP determinístico (extract_conversation)
  3. Estado Conversacional (EstadoConversacional)
  4. Resolutor de Variables Faltantes (resolver_siguiente_variable)
  5. Policy Engine / FSM (evaluar_transicion_estado)
  6. Generador de Respuestas Contextuales (generar_respuesta_contextual)
"""

from __future__ import annotations
from dataclasses import dataclass, field
import re
import unicodedata

from services.extraction_service import (
    extract_conversation,
    extract_motocicleta,
    extract_pago_inicial,
    extract_metodo_pago,
    extract_solicita_cotizacion,
    extract_solicita_cita,
    _normalizar_texto,
    _obtener_textos_usuario,
)

# ── Estados de Información ───────────────────────────────────────────────────
DESCONOCIDO = "DESCONOCIDO"
CONOCIDO = "CONOCIDO"
CONFIRMADO = "CONFIRMADO"
AMBIGUO = "AMBIGUO"
CAMBIADO = "CAMBIADO"
NO_APLICA = "NO_APLICA"

# ── Estados de FSM ────────────────────────────────────────────────────────────
FSM_INICIO = "INICIO"
FSM_CAPTURANDO_MODELO = "CAPTURANDO_MODELO"
FSM_MODELO_DEFINIDO = "MODELO_DEFINIDO"
FSM_EVALUANDO_PAGO = "EVALUANDO_PAGO"
FSM_AGENDANDO_CITA = "AGENDANDO_CITA"
FSM_CITA_CONFIRMADA = "CITA_CONFIRMADA"
FSM_FINALIZADO_ASESOR = "FINALIZADO_ASESOR"

# ── Enum de Preguntas Pendientes ──────────────────────────────────────────────
PREG_NINGUNA = "NINGUNA"
PREG_SELECCIONAR_MODELO = "SELECCIONAR_MODELO"
PREG_CONFIRMAR_METODO_PAGO = "CONFIRMAR_METODO_PAGO"
PREG_SOLICITAR_PAGO_INICIAL = "SOLICITAR_PAGO_INICIAL"
PREG_SOLICITAR_COTIZACION = "SOLICITAR_COTIZACION"
PREG_CONFIRMAR_CITA = "CONFIRMAR_CITA"
PREG_SOLICITAR_SEDE = "SOLICITAR_SEDE"

# ── Enum de Variables Faltantes ───────────────────────────────────────────────
VAR_MODELO = "modelo_interes"
VAR_PAGO = "metodo_pago"
VAR_INICIAL = "pago_inicial"
VAR_COTIZACION = "solicita_cotizacion"
VAR_CITA = "solicita_cita"
VAR_SEDE = "ciudad_sede"
VAR_FINALIZADO = "FINALIZADO_ASESOR"

# Ciudades / Sedes conocidas en el sistema (Armenia, Bogotá, Medellín, Cali, etc.)
SEDES_CONOCIDAS = [
    "armenia", "bogota", "medellin", "cali", "barranquilla", "pereira",
    "bucaramanga", "manizales", "cartagena", "ibague", "villavicencio"
]

AFIRMATIVOS = ["si", "sí", "claro", "correcto", "dale", "por supuesto", "de acuerdo", "efectivamente", "me gustaria", "quisiera"]
NEGATIVOS = ["no", "nop", "por ahora no", "no gracias", "mas adelante", "despues"]


@dataclass
class EstadoConversacional:
    """Estructura de datos para el seguimiento del estado de la conversación."""
    modelo_interes: str | None = None  # SKU de la moto
    nombre_modelo: str | None = None   # Nombre legible de la moto
    estado_modelo: str = DESCONOCIDO
    
    metodo_pago: str | None = None     # 'Contado' | 'Crédito'
    estado_pago: str = DESCONOCIDO
    
    pago_inicial: int | None = None    # Monto numérico
    estado_inicial: str = DESCONOCIDO
    
    solicita_cotizacion: bool | None = None  # True | False | None
    solicita_cita: bool | None = None        # True | False | None
    
    ciudad_sede: str | None = None
    estado_sede: str = DESCONOCIDO
    
    pregunta_pendiente: str = PREG_NINGUNA
    estado_fsm: str = FSM_INICIO
    historial_modelos: list[str] = field(default_factory=list)
    intencion_actual: str | None = None

    def __post_init__(self):
        if self.modelo_interes and self.estado_modelo == DESCONOCIDO:
            self.estado_modelo = CONOCIDO

    def to_dict(self) -> dict:
        return {
            "modelo_interes": self.modelo_interes,
            "nombre_modelo": self.nombre_modelo,
            "estado_modelo": self.estado_modelo,
            "metodo_pago": self.metodo_pago,
            "estado_pago": self.estado_pago,
            "pago_inicial": self.pago_inicial,
            "estado_inicial": self.estado_inicial,
            "solicita_cotizacion": self.solicita_cotizacion,
            "solicita_cita": self.solicita_cita,
            "ciudad_sede": self.ciudad_sede,
            "estado_sede": self.estado_sede,
            "pregunta_pendiente": self.pregunta_pendiente,
            "estado_fsm": self.estado_fsm,
            "historial_modelos": self.historial_modelos,
            "intencion_actual": self.intencion_actual,
        }

    @classmethod
    def from_dict(cls, data: dict) -> EstadoConversacional:
        if not data:
            return cls()
        return cls(
            modelo_interes=data.get("modelo_interes"),
            nombre_modelo=data.get("nombre_modelo"),
            estado_modelo=data.get("estado_modelo", DESCONOCIDO),
            metodo_pago=data.get("metodo_pago"),
            estado_pago=data.get("estado_pago", DESCONOCIDO),
            pago_inicial=data.get("pago_inicial"),
            estado_inicial=data.get("estado_inicial", DESCONOCIDO),
            solicita_cotizacion=data.get("solicita_cotizacion"),
            solicita_cita=data.get("solicita_cita"),
            ciudad_sede=data.get("ciudad_sede"),
            estado_sede=data.get("estado_sede", DESCONOCIDO),
            pregunta_pendiente=data.get("pregunta_pendiente", PREG_NINGUNA),
            estado_fsm=data.get("estado_fsm", FSM_INICIO),
            historial_modelos=data.get("historial_modelos", []),
            intencion_actual=data.get("intencion_actual"),
        )


def resolver_siguiente_variable(estado: EstadoConversacional) -> str:
    """
    Determina dinámicamente la siguiente variable comercial faltante
    respetando el orden estricto de prioridad comercial.
    """
    # 1. Modelo de Interés (Obligatorio primero)
    if estado.estado_modelo in (DESCONOCIDO, AMBIGUO):
        return VAR_MODELO

    # 2. Método de Pago (Contado vs Crédito)
    if estado.metodo_pago is None:
        return VAR_PAGO

    # 3. Pago Inicial (Solo si Método de Pago == 'Crédito')
    if (
        estado.metodo_pago == "Crédito"
        and estado.pago_inicial is None
        and estado.estado_inicial not in (NO_APLICA, CONFIRMADO)
    ):
        return VAR_INICIAL

    # 4. Cotización (Solicitud explícita)
    if estado.solicita_cotizacion is None:
        return VAR_COTIZACION

    # 5. Cita en Concesionario
    if estado.solicita_cita is None:
        return VAR_CITA

    # 6. Ciudad / Sede (Solo si solicita_cita == True)
    if estado.solicita_cita is True and estado.ciudad_sede is None:
        return VAR_SEDE

    # 7. Si todo está completo -> Asesor
    return VAR_FINALIZADO


def _obtener_nombre_modelo(sku: str | None, catalogo: list[dict]) -> str | None:
    if not sku or not catalogo:
        return None
    for moto in catalogo:
        if moto.get("sku") == sku:
            linea = moto.get("linea") or moto.get("modelo") or sku
            marca = moto.get("marca") or ""
            if marca and marca.lower() not in linea.lower():
                return f"{marca} {linea}"
            return linea
    return sku


def _obtener_precio_modelo(sku: str | None, catalogo: list[dict]) -> int | None:
    if not sku or not catalogo:
        return None
    for moto in catalogo:
        if moto.get("sku") == sku:
            return moto.get("precio_lista") or moto.get("precio")
    return None


def _detectar_ambiguedad_modelos(texto_norm: str, catalogo: list[dict]) -> list[str]:
    """Detecta si el usuario mencionó más de un modelo en el mismo texto."""
    coincidencias = []
    for moto in catalogo:
        linea = _normalizar_texto(moto.get("linea") or "")
        tokens = linea.split()
        palabra_principal = tokens[0] if tokens else ""
        if palabra_principal and len(palabra_principal) >= 3:
            if re.search(r'\b' + re.escape(palabra_principal) + r'\b', texto_norm):
                sku = moto["sku"]
                if sku not in coincidencias:
                    coincidencias.append(sku)
    return coincidencias


def _detectar_ciudad_sede(texto_raw: str) -> str | None:
    texto_norm = _normalizar_texto(texto_raw)
    for ciudad in SEDES_CONOCIDAS:
        if re.search(r'\b' + re.escape(ciudad) + r'\b', texto_norm):
            return ciudad.capitalize()
    return None


def _extraer_monto_directo(texto_norm: str, texto_raw: str) -> int | None:
    """Extrae montos de cuota inicial incluso si no contienen explícitamente la palabra 'inicial'."""
    from services.extraction_service import NUMEROS_TEXTO
    m_palo = re.search(r'\b(\d+(?:[.,]\d+)?)\s*palo(?:s)?\b', texto_norm)
    if m_palo:
        try:
            return int(float(m_palo.group(1).replace(',', '.')) * 1_000_000)
        except ValueError:
            pass
    m_mil = re.search(r'(\d+(?:[.,]\d+)?)\s*millon(?:es)?', texto_norm)
    if m_mil:
        try:
            return int(float(m_mil.group(1).replace(',', '.')) * 1_000_000)
        except ValueError:
            pass
    m_word = re.search(r'\b(un|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\s*millon(?:es)?\b', texto_norm)
    if m_word:
        num = NUMEROS_TEXTO.get(m_word.group(1))
        if num:
            return num * 1_000_000
    m_dots = re.search(r'\$?\s*(\d{1,3}(?:\.\d{3})+)', texto_raw)
    if m_dots:
        try:
            return int(m_dots.group(1).replace('.', ''))
        except ValueError:
            pass
    m_plain = re.search(r'\b(\d{6,8})\b', texto_raw)
    if m_plain:
        try:
            return int(m_plain.group(1))
        except ValueError:
            pass
    return None


def actualizar_estado_desde_nlp(
    estado: EstadoConversacional,
    messages: list[dict],
    catalogo: list[dict]
) -> EstadoConversacional:
    """
    Integra la información extraída por NLP de forma incremental en el estado,
    manejando cambios de modelo, respuestas de contado y atajos.
    """
    textos_usuario = _obtener_textos_usuario(messages)
    ultimo_texto_raw = textos_usuario[-1] if textos_usuario else ""
    ultimo_texto_norm = _normalizar_texto(ultimo_texto_raw)

    # 1. Detección de Ambigüedad
    modelos_coincidentes = _detectar_ambiguedad_modelos(ultimo_texto_norm, catalogo)
    if len(modelos_coincidentes) > 1 and (" vs " in ultimo_texto_norm or " o " in ultimo_texto_norm or "entre" in ultimo_texto_norm):
        estado.estado_modelo = AMBIGUO
        return estado

    # 2. Extracción de Modelo (Evaluando mensaje más reciente primero para cambios de modelo)
    ultimo_msg_list = [{"role": "user", "content": ultimo_texto_raw}]
    sku_detectado_ultimo = extract_motocicleta(ultimo_msg_list, catalogo)
    sku_detectado_historial = extract_motocicleta(messages, catalogo)
    sku_detectado = sku_detectado_ultimo or sku_detectado_historial

    if sku_detectado:
        if estado.modelo_interes and estado.modelo_interes != sku_detectado:
            # Cambio de modelo explícito
            if estado.modelo_interes not in estado.historial_modelos:
                estado.historial_modelos.append(estado.modelo_interes)
            estado.modelo_interes = sku_detectado
            estado.nombre_modelo = _obtener_nombre_modelo(sku_detectado, catalogo)
            estado.estado_modelo = CAMBIADO
        else:
            estado.modelo_interes = sku_detectado
            estado.nombre_modelo = _obtener_nombre_modelo(sku_detectado, catalogo)
            if estado.estado_modelo != CONFIRMADO:
                estado.estado_modelo = CONOCIDO

    # 3. Método de Pago (incluyendo expresiones de contado coloquiales)
    patrones_contado_extra = ["contado", "al contado", "efectivo", "en efectivo", "voy a pagar todo", "pagar todo", "de una", "sin credito", "sin crédito", "pago unico", "un solo pago"]
    if any(p in ultimo_texto_norm for p in patrones_contado_extra):
        if estado.metodo_pago == "Contado":
            estado.estado_pago = CONFIRMADO
        else:
            estado.metodo_pago = "Contado"
            estado.estado_pago = CONOCIDO
        estado.pago_inicial = None
        estado.estado_inicial = NO_APLICA
    else:
        metodo_pago_nlp = extract_metodo_pago(messages)
        if metodo_pago_nlp:
            if estado.metodo_pago and estado.metodo_pago != metodo_pago_nlp:
                estado.metodo_pago = metodo_pago_nlp
                estado.estado_pago = CAMBIADO
            else:
                estado.metodo_pago = metodo_pago_nlp
                estado.estado_pago = CONOCIDO
            if metodo_pago_nlp == "Contado":
                estado.pago_inicial = None
                estado.estado_inicial = NO_APLICA

    # 4. Pago Inicial (Solo relevante para Crédito)
    if estado.metodo_pago == "Crédito":
        inicial_nlp = extract_pago_inicial(messages) or _extraer_monto_directo(ultimo_texto_norm, ultimo_texto_raw)
        if inicial_nlp is not None:
            estado.pago_inicial = inicial_nlp
            estado.estado_inicial = CONOCIDO

    # 5. Cotización
    cot_nlp = extract_solicita_cotizacion(messages)
    if cot_nlp is not None and estado.solicita_cotizacion is None:
        estado.solicita_cotizacion = cot_nlp

    # 6. Cita
    cita_nlp = extract_solicita_cita(messages)
    if cita_nlp is not None and estado.solicita_cita is None:
        estado.solicita_cita = cita_nlp

    # 7. Sede / Ciudad
    ciudad_detectada = _detectar_ciudad_sede(ultimo_texto_raw)
    if ciudad_detectada:
        estado.ciudad_sede = ciudad_detectada
        estado.estado_sede = CONOCIDO

    return estado


def procesar_respuesta_corta(
    estado: EstadoConversacional,
    ultimo_texto_norm: str
) -> tuple[EstadoConversacional, bool]:
    """
    Procesa respuestas cortas ("sí", "no") priorizando la `pregunta_pendiente`.
    Retorna tuple(estado_actualizado, fue_procesada).
    """
    es_afirmativo = any(re.search(r'\b' + re.escape(w) + r'\b', ultimo_texto_norm) for w in AFIRMATIVOS)
    es_negativo = any(re.search(r'\b' + re.escape(w) + r'\b', ultimo_texto_norm) for w in NEGATIVOS)

    if not es_afirmativo and not es_negativo:
        return estado, False

    preg = estado.pregunta_pendiente

    if preg == PREG_SOLICITAR_COTIZACION:
        estado.solicita_cotizacion = True if es_afirmativo else False
        estado.pregunta_pendiente = PREG_NINGUNA
        return estado, True

    elif preg == PREG_CONFIRMAR_CITA:
        if es_afirmativo:
            estado.solicita_cita = True
            estado.estado_fsm = FSM_AGENDANDO_CITA
        else:
            estado.solicita_cita = False
        estado.pregunta_pendiente = PREG_NINGUNA
        return estado, True

    elif preg == PREG_SOLICITAR_SEDE and es_afirmativo:
        # "sí" cuando se le preguntó la sede (ej. "¿Te queda bien Armenia?")
        estado.ciudad_sede = estado.ciudad_sede or "Armenia"
        estado.estado_sede = CONFIRMADO
        estado.pregunta_pendiente = PREG_NINGUNA
        return estado, True

    elif preg == PREG_CONFIRMAR_METODO_PAGO:
        # Sí/No a método de pago -> No determina si es contado o crédito
        return estado, False

    return estado, False


def generar_respuesta_contextual(
    estado: EstadoConversacional,
    siguiente_var: str,
    catalogo: list[dict],
    ultimo_texto_raw: str
) -> str:
    """
    Capa 6: Generador de Respuestas en lenguaje natural dinámico,
    breves, comerciales y contextuales.
    """
    ultimo_texto_norm = _normalizar_texto(ultimo_texto_raw)

    # 1. Manejo de Ambigüedad
    if estado.estado_modelo == AMBIGUO:
        estado.pregunta_pendiente = PREG_SELECCIONAR_MODELO
        return "Ambas son excelentes opciones. ¿Sobre cuál de los modelos te gustaría recibir la información detalada y cotización?"

    # 2. Solicitud explícita de Asesor por parte del usuario
    if any(w in ultimo_texto_norm for w in ["asesor", "llamen", "llamar", "contacten", "hablar con alguien", "hablar con un asesor"]):
        estado.estado_fsm = FSM_FINALIZADO_ASESOR
        estado.pregunta_pendiente = PREG_NINGUNA
        if estado.ciudad_sede:
            return f"Con gusto te conectamos con un asesor comercial de nuestra sede de {estado.ciudad_sede}. Se pondrá en contacto contigo a la brevedad."
        return "Con gusto te conectamos con un asesor comercial. ¿En qué ciudad o sede prefieres que te contacten?"

    # 3. Generación según la siguiente variable faltante
    if siguiente_var == VAR_MODELO:
        estado.pregunta_pendiente = PREG_SELECCIONAR_MODELO
        estado.estado_fsm = FSM_CAPTURANDO_MODELO
        
        # Ofrecer catálogo si el usuario no especificó modelo
        modelos_destacados = []
        if catalogo:
            modelos_destacados = [m.get("linea") or m.get("modelo") for m in catalogo[:4] if m.get("linea")]
        
        if modelos_destacados:
            lista_str = ", ".join(modelos_destacados)
            return f"¡Hola! Bienvenido a Motos AI. ¿En qué modelo de motocicleta estás interesado hoy? Tenemos disponibles referencias como: {lista_str} y más."
        return "¡Hola! Bienvenido a Motos AI. ¿En qué modelo de motocicleta estás interesado hoy?"

    nombre = estado.nombre_modelo or "la motocicleta"
    precio = _obtener_precio_modelo(estado.modelo_interes, catalogo)
    precio_str = f"${precio:,.0f}".replace(",", ".") if precio else None

    if siguiente_var == VAR_PAGO:
        estado.pregunta_pendiente = PREG_CONFIRMAR_METODO_PAGO
        estado.estado_fsm = FSM_MODELO_DEFINIDO
        
        prefix = ""
        if estado.estado_modelo == CAMBIADO:
            prefix = f"Entendido, actualizamos tu interés a la {nombre}. "
        elif precio_str:
            prefix = f"Excelente elección. La {nombre} tiene un precio de lista de {precio_str}. "
        else:
            prefix = f"Excelente elección. "

        return f"{prefix}¿Cómo deseas realizar la compra: de contado o mediante financiación?"

    if siguiente_var == VAR_INICIAL:
        estado.pregunta_pendiente = PREG_SOLICITAR_PAGO_INICIAL
        estado.estado_fsm = FSM_EVALUANDO_PAGO
        return f"Perfecto, registramos opción a crédito para la {nombre}. ¿Con cuánto dinero cuentas aproximadamente para la cuota inicial?"

    if siguiente_var == VAR_COTIZACION:
        estado.pregunta_pendiente = PREG_SOLICITAR_COTIZACION
        
        prefix = ""
        if estado.metodo_pago == "Crédito" and estado.pago_inicial:
            inicial_str = f"${estado.pago_inicial:,.0f}".replace(",", ".")
            prefix = f"Registramos una cuota inicial de {inicial_str} para tu crédito. "
        elif estado.metodo_pago == "Contado":
            prefix = f"Perfecto, registramos tu opción de pago de contado. "
            
        return f"{prefix}¿Deseas que te generemos una cotización formal?"

    if siguiente_var == VAR_CITA:
        estado.pregunta_pendiente = PREG_CONFIRMAR_CITA
        estado.estado_fsm = FSM_AGENDANDO_CITA
        return f"¿Te gustaría agendar una cita en el concesionario para ver la {nombre} y probarla?"

    if siguiente_var == VAR_SEDE:
        estado.pregunta_pendiente = PREG_SOLICITAR_SEDE
        estado.estado_fsm = FSM_AGENDANDO_CITA
        return f"¡Excelente! ¿En qué ciudad o sede de concesionario prefieres tu cita?"

    if siguiente_var == VAR_FINALIZADO:
        estado.pregunta_pendiente = PREG_NINGUNA
        estado.estado_fsm = FSM_CITA_CONFIRMADA
        
        sede_txt = f" en la sede de {estado.ciudad_sede}" if estado.ciudad_sede else ""
        return f"¡Todo listo! Registramos tu solicitud para la {nombre}{sede_txt}. Un asesor comercial se pondrá en contacto contigo a la brevedad."

    # Fallback contextual de seguridad
    estado.pregunta_pendiente = PREG_NINGUNA
    return f"Entendido. Sobre la {nombre}, ¿te gustaría conocer el precio, opciones de financiación o agendar una cita?"


def process_turn(
    session_messages: list[dict],
    catalogo: list[dict],
    estado_previo: EstadoConversacional | None = None
) -> tuple[str, EstadoConversacional]:
    """
    Función de entrada principal de la pipeline conversacional.
    Toma los mensajes acumulados de la sesión y actualiza el estado.
    Retorna tuple(bot_response_text, nuevo_estado).
    """
    estado = estado_previo or EstadoConversacional()

    textos_usuario = _obtener_textos_usuario(session_messages)
    if not textos_usuario:
        res = "¡Hola! Bienvenido a Motos AI. ¿En qué modelo de motocicleta estás interesado hoy?"
        estado.pregunta_pendiente = PREG_SELECCIONAR_MODELO
        return res, estado

    ultimo_texto_raw = textos_usuario[-1]
    ultimo_texto_norm = _normalizar_texto(ultimo_texto_raw)

    # 1. Procesar respuestas afirmativas/negativas cortas según pregunta_pendiente
    estado, fue_corta = procesar_respuesta_corta(estado, ultimo_texto_norm)

    # 2. Actualizar estado con información extraída de NLP
    estado = actualizar_estado_desde_nlp(estado, session_messages, catalogo)

    # 3. Resolver la siguiente variable faltante
    siguiente_var = resolver_siguiente_variable(estado)

    # 4. Generar respuesta contextual
    bot_text = generar_respuesta_contextual(estado, siguiente_var, catalogo, ultimo_texto_raw)

    return bot_text, estado


def build_extraction_view(
    estado: EstadoConversacional,
    raw_extraction: dict | None = None
) -> dict:
    """
    Construye la vista de extracción acumulada unificando
    la extracción NLP determinística y el EstadoConversacional.
    """
    raw = raw_extraction or {}

    sku = estado.modelo_interes or raw.get("sku_motocicleta")
    metodo = estado.metodo_pago or raw.get("metodo_pago")

    pago_init = estado.pago_inicial
    if metodo == "Contado" or estado.estado_inicial == NO_APLICA:
        pago_init = "NO_APLICA"
    elif pago_init is None:
        pago_init = raw.get("pago_inicial")

    cot = estado.solicita_cotizacion
    if cot is None:
        cot = raw.get("solicita_cotizacion")

    cita = estado.solicita_cita
    if cita is None:
        cita = raw.get("solicita_cita")

    sede = estado.ciudad_sede

    intencion = estado.intencion_actual or raw.get("intencion_declarada")
    if intencion is None and (sku or cot or cita or metodo):
        intencion = "Compra"

    return {
        "sku_motocicleta": sku,
        "pago_inicial": pago_init,
        "metodo_pago": metodo,
        "intencion_declarada": intencion,
        "objecion_principal": raw.get("objecion_principal"),
        "solicita_cotizacion": cot,
        "solicita_cita": cita,
        "ciudad_sede": sede,
    }
