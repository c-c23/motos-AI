"""
ai/gemini_extractor.py
----------------------
Extractor semántico con Gemini (API oficial google-genai) y mecanismo de fallback
robusto hacia el extractor determinista por reglas.
"""

from __future__ import annotations
import os
import json
import logging
from typing import Any
from dotenv import load_dotenv

# Cargar variables de entorno si están disponibles en .env
load_dotenv()

from ai.schemas import AnalisisSemantico, ResultadoExtraccion
from services.extraction_service import extract_conversation

logger = logging.getLogger("ai.gemini_extractor")

DEFAULT_MODEL = "gemini-3.8-flash"
EXTRACTION_VERSION = "1.0"

SYSTEM_PROMPT = """Eres un analista experto en inteligencia comercial para la industria de motocicletas en Colombia.
Tu tarea es analizar detalladamente el texto de una conversación entre un cliente potencial (lead) y un asesor/bot de concesionario de motos, extrayendo señales semánticas y comerciales precisas.

Analiza ÚNICAMENTE la evidencia contenida en la conversación.

Debes evaluar:
1. `intencion_compra`:
   - "alta": El cliente muestra intención firme de adquirir la motocicleta (cuenta con dinero para inicial, pide separar la moto, confirma que va en camino o solicita visita inmediata para compra).
   - "media": El cliente tiene interés concreto, pide cotización, pregunta cuotas o requisitos, pero no ha confirmado compra inmediata.
   - "baja": El cliente solo está mirando precios o curioseando sin intención de avance.
   - "indeterminada": El texto es insuficiente o no permite inferir la intención.

2. `urgencia`:
   - "alta": Acciones para hoy mismo, inmediatas ("ya voy en camino", "¿a qué hora puedo ir hoy?").
   - "media": Plan de compra o visita en el corto plazo (esta semana, próximos días).
   - "baja": Sin prisa o a largo plazo.
   - "indeterminada": No se expresa ningún marco de tiempo.

3. `fase_embudo`:
   - "exploracion": Solo mirando catálogo/precios sin modelo definido o en dudas iniciales.
   - "interes": Pregunta por un modelo específico o características.
   - "evaluacion": Evalúa opciones de pago, compara modelos o pregunta requisitos.
   - "cotizacion": Solicita formalmente que le envíen precio, plan de cuotas o cotización.
   - "visita": Agenda o confirma visita física al concesionario.
   - "compra": En proceso de cierre, separación o pago.
   - "indeterminada": No clasificable.

4. `solicita_asesor`: True si pide hablar o ser contactado por un asesor humano; False de lo contrario.
5. `solicita_cotizacion`: True si pide cotización, costos o cuota mensual; False de lo contrario.
6. `solicita_cita`: True si manifiesta intención de ir, probar la moto o agendar cita en la sede; False de lo contrario.
7. `objecion_principal`: Objeción detectada (ej. "Tasa de interés elevada", "Precio fuera de presupuesto", "Requisitos de crédito") o null si no existe.
8. `senales_compra`: Lista de frases o hechos explícitos sustentados en el texto que respaldan la intención de compra (ej. "Tiene 4 palos para cuota inicial", "Contrato indefinido", "Va en camino a la sede").
9. `confianza`: Número flotante entre 0.0 y 1.0 que indica la certidumbre del análisis.

REGLAS CRÍTICAS:
- No inventar información ni asumir capacidad económica no expresada.
- Diferenciar hechos explícitos de inferencias.
- Las `senales_compra` deben estar sustentadas directamente en el texto.
- Generar estrictamente la respuesta en formato JSON de acuerdo con el esquema especificado.
"""


def _formatear_mensajes_para_prompt(mensajes: Any) -> str:
    """Convierte cualquier formato de entrada (str, list[str], list[dict]) a texto formateado."""
    if isinstance(mensajes, str):
        return mensajes.strip()
    
    if isinstance(mensajes, list):
        lineas = []
        for item in mensajes:
            if isinstance(item, str):
                lineas.append(item.strip())
            elif isinstance(item, dict):
                role = item.get("role") or item.get("remitente") or "usuario"
                content = item.get("content") or item.get("texto") or ""
                rol_str = "Cliente" if role in ("user", "cliente", "Cliente") else "Asesor"
                lineas.append(f"{rol_str}: {content}")
        return "\n".join(lineas)
    
    return str(mensajes)


def _convertir_a_lista_dicts(mensajes: Any) -> list[dict]:
    """Convierte la entrada a la estructura list[dict] esperada por el extractor determinista."""
    if isinstance(mensajes, list) and all(isinstance(m, dict) for m in mensajes):
        return mensajes

    if isinstance(mensajes, list) and all(isinstance(m, str) for m in mensajes):
        return [{"role": "user", "content": s} for s in mensajes]

    if isinstance(mensajes, str):
        lineas = [l.strip() for l in mensajes.split("\n") if l.strip()]
        result = []
        for l in lineas:
            if l.lower().startswith("cliente:") or l.lower().startswith("user:"):
                result.append({"role": "user", "content": l.split(":", 1)[1].strip()})
            elif l.lower().startswith("asesor:") or l.lower().startswith("bot:"):
                result.append({"role": "assistant", "content": l.split(":", 1)[1].strip()})
            else:
                result.append({"role": "user", "content": l})
        return result

    return [{"role": "user", "content": str(mensajes)}]


def _obtener_cliente_gemini(client: Any = None) -> Any:
    """Instancia el cliente oficial de Gemini validando la presencia de GEMINI_API_KEY."""
    if client is not None:
        return client

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not api_key.strip():
        raise ValueError("GEMINI_API_KEY no configurada o vacía en el entorno.")

    from google import genai
    return genai.Client(api_key=api_key)


def extraer_analisis_semantico_gemini(
    mensajes: Any,
    client: Any = None,
    model: str = DEFAULT_MODEL
) -> AnalisisSemantico:
    """
    Invoca Gemini usando la API oficial y valida la respuesta contra el esquema AnalisisSemantico.
    Lanza excepciones en caso de error de red, API key faltante o JSON inválido.
    """
    gemini_client = _obtener_cliente_gemini(client)
    conversacion_texto = _formatear_mensajes_para_prompt(mensajes)

    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"--- CONVERSACIÓN A ANALIZAR ---\n"
        f"{conversacion_texto}\n"
        f"--- FIN DE CONVERSACIÓN ---\n\n"
        f"Extrae el análisis semántico estrictamente según el esquema JSON solicitado."
    )

    interaction = gemini_client.interactions.create(
        model=model,
        input=prompt,
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": AnalisisSemantico.model_json_schema()
        }
    )

    output_raw = getattr(interaction, "output_text", None)
    if not output_raw and hasattr(interaction, "text"):
        output_raw = interaction.text

    if not output_raw:
        raise ValueError("Gemini devolvió una respuesta vacía sin texto.")

    # Validación Pydantic
    return AnalisisSemantico.model_validate_json(output_raw)


def _crear_analisis_fallback(extraccion_reglas: dict) -> AnalisisSemantico:
    """Mapea los datos del extractor determinista al esquema AnalisisSemantico en modo fallback."""
    intencion = extraccion_reglas.get("intencion_declarada")
    solicita_cot = extraccion_reglas.get("solicita_cotizacion")
    solicita_cit = extraccion_reglas.get("solicita_cita")
    sku = extraccion_reglas.get("sku_motocicleta")

    # Inferencia conservadora por reglas
    if intencion == "Compra" or solicita_cit is True:
        intencion_compra = "alta"
    elif solicita_cot is True or sku is not None:
        intencion_compra = "media"
    elif intencion == "Consulta":
        intencion_compra = "baja"
    else:
        intencion_compra = "indeterminada"

    if solicita_cit is True:
        fase = "visita"
    elif solicita_cot is True:
        fase = "cotizacion"
    elif sku is not None:
        fase = "interes"
    else:
        fase = "exploracion" if intencion == "Consulta" else "indeterminada"

    return AnalisisSemantico(
        intencion_compra=intencion_compra,
        urgencia="indeterminada",
        fase_embudo=fase,
        solicita_asesor=False,
        solicita_cotizacion=bool(solicita_cot) if solicita_cot is not None else False,
        solicita_cita=bool(solicita_cit) if solicita_cit is not None else False,
        objecion_principal=None,
        senales_compra=[],
        confianza=0.5
    )


def analizar_conversacion(
    mensajes: Any,
    catalogo: list[dict] | None = None,
    client: Any = None,
    model: str = DEFAULT_MODEL
) -> ResultadoExtraccion:
    """
    Función de alto nivel con flujo principal Gemini y fallback garantizado:
    
    1. Intenta Gemini -> Validación Pydantic -> Resultado IA (modelo_extraccion='gemini')
    2. Si falla (sin API key, timeout, error de red, error de esquema, etc.) ->
       Fallback a extractor determinista (modelo_extraccion='reglas')
    """
    catalogo_lista = catalogo or []
    mensajes_dict = _convertir_a_lista_dicts(mensajes)
    extraccion_reglas = extract_conversation(mensajes_dict, catalogo_lista)

    try:
        analisis_semantico = extraer_analisis_semantico_gemini(
            mensajes=mensajes,
            client=client,
            model=model
        )

        return ResultadoExtraccion(
            modelo_extraccion="gemini",
            version_extraccion=EXTRACTION_VERSION,
            analisis_semantico=analisis_semantico,
            sku_motocicleta=extraccion_reglas.get("sku_motocicleta"),
            metodo_pago=extraccion_reglas.get("metodo_pago"),
            pago_inicial=extraccion_reglas.get("pago_inicial"),
            intencion_declarada=extraccion_reglas.get("intencion_declarada"),
            error_detalle=None
        )

    except Exception as exc:
        logger.warning("Fallo en extracción Gemini, activando fallback a reglas: %s", exc)
        analisis_fallback = _crear_analisis_fallback(extraccion_reglas)

        return ResultadoExtraccion(
            modelo_extraccion="reglas",
            version_extraccion=EXTRACTION_VERSION,
            analisis_semantico=analisis_fallback,
            sku_motocicleta=extraccion_reglas.get("sku_motocicleta"),
            metodo_pago=extraccion_reglas.get("metodo_pago"),
            pago_inicial=extraccion_reglas.get("pago_inicial"),
            intencion_declarada=extraccion_reglas.get("intencion_declarada"),
            error_detalle=str(exc)
        )
