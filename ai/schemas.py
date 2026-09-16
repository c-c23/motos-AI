"""
ai/schemas.py
-------------
Esquemas Pydantic para la extracción y análisis semántico de conversaciones comerciales.
"""

from typing import Literal, Optional, List
from pydantic import BaseModel, Field, ConfigDict


IntencionCompraType = Literal["baja", "media", "alta", "indeterminada"]
UrgenciaType = Literal["baja", "media", "alta", "indeterminada"]
FaseEmbudoType = Literal[
    "exploracion",
    "interes",
    "evaluacion",
    "cotizacion",
    "visita",
    "compra",
    "indeterminada"
]


class AnalisisSemantico(BaseModel):
    """
    Esquema validado por Pydantic que captura señales semánticas
    extraídas por Gemini desde el texto de la conversación.
    """
    model_config = ConfigDict(extra="forbid")

    intencion_compra: IntencionCompraType = Field(
        ...,
        description="Nivel de intención de compra detectado: baja, media, alta, indeterminada"
    )
    urgencia: UrgenciaType = Field(
        ...,
        description="Nivel de urgencia o inmediatez temporal del cliente: baja, media, alta, indeterminada"
    )
    fase_embudo: FaseEmbudoType = Field(
        ...,
        description="Fase del embudo comercial en la que se encuentra el cliente"
    )
    solicita_asesor: bool = Field(
        ...,
        description="True si el cliente pide explícitamente hablar o ser contactado por un asesor comercial"
    )
    solicita_cotizacion: bool = Field(
        ...,
        description="True si el cliente solicita cotización de precio, cuotas o costos"
    )
    solicita_cita: bool = Field(
        ...,
        description="True si el cliente solicita o confirma una cita o visita al concesionario"
    )
    objecion_principal: Optional[str] = Field(
        default=None,
        description="Principal objeción comercial detectada (ej. intereses altos, precio, requisitos) o None si no hay"
    )
    senales_compra: List[str] = Field(
        default_factory=list,
        description="Lista de señales explícitas de compra basadas estrictamente en la evidencia del texto"
    )
    confianza: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Nivel de confianza global del análisis semántico entre 0.0 y 1.0"
    )


class ResultadoExtraccion(BaseModel):
    """
    Resultado global de la extracción con metadatos de trazabilidad,
    variables semánticas y entidades comerciales.
    """
    modelo_extraccion: Literal["gemini", "reglas"] = Field(
        ...,
        description="Mecanismo utilizado para la extracción: 'gemini' o 'reglas' (fallback)"
    )
    version_extraccion: str = Field(
        default="1.0",
        description="Versión del motor de extracción"
    )
    analisis_semantico: AnalisisSemantico = Field(
        ...,
        description="Análisis semántico validado (producido por Gemini o mapeado en fallback)"
    )
    sku_motocicleta: Optional[str] = Field(
        default=None,
        description="SKU de la motocicleta identificada"
    )
    metodo_pago: Optional[str] = Field(
        default=None,
        description="Método de pago: 'Contado', 'Crédito' o None"
    )
    pago_inicial: Optional[int] = Field(
        default=None,
        description="Monto numérico de cuota inicial o 0 si declara no tener inicial"
    )
    intencion_declarada: Optional[str] = Field(
        default=None,
        description="Intención declarada según extractor tradicional ('Compra', 'Consulta', None)"
    )
    error_detalle: Optional[str] = Field(
        default=None,
        description="Detalle del error si se activó el fallback"
    )
