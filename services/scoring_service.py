"""
services/scoring_service.py
----------------------------
Servicio para cálculo e implementación del Scoring Híbrido de prioridad operacional.
- Modelo Principal: Logistic Regression V1 (entrenado en dataset histórico independiente HX-...)
- Modelo Fallback: Rules V1 (basado en tramos deterministas de respuesta, cita y cuota)

Selección dinámica del modelo:
  - Si existen extracciones conversacionales (o variables estructuradas): Logistic Regression V1
  - Si no existen suficientes extracciones: Rules V1 (fallback)
"""

from __future__ import annotations
import os
import math
from datetime import datetime
from decimal import Decimal
import joblib
import numpy as np
import psycopg
from typing import Any

from database import get_connection
from queries.scoring_queries import (
    get_lead_data_for_scoring,
    guardar_puntaje_lead_trx,
    guardar_puntaje_v2_lead_trx,
)

# Cargar artefacto de Regresión Logística V1 si existe
MODEL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models", "logistic_regression_v1.joblib"))
LR_PACKAGE = None
if os.path.exists(MODEL_PATH):
    try:
        LR_PACKAGE = joblib.load(MODEL_PATH)
    except Exception as e:
        LR_PACKAGE = None


def calcular_horas_sin_contacto(
    registrado_en: datetime,
    primer_contacto_en: datetime | None = None,
    fecha_referencia: datetime | None = None,
) -> tuple[float, str]:
    """
    Calcula las horas transcurridas desde el registro.
    - Si el lead ya fue contactado (primer_contacto_en IS NOT NULL), se calcula el intervalo
      histórico entre registrado_en y primer_contacto_en.
    - Si el lead NO ha sido contactado (primer_contacto_en IS NULL), se calcula el tiempo
      transcurrido entre registrado_en y la fecha actual / referencia.

    Returns:
        tuple (horas: float, tipo_contacto: str)
    """
    if not registrado_en:
        return 0.0, "no_contactado"

    if primer_contacto_en:
        delta = (primer_contacto_en - registrado_en).total_seconds()
        horas = max(0.0, delta / 3600.0)
        return round(horas, 2), "contactado"
    else:
        ref = fecha_referencia or datetime.now()
        delta = (ref - registrado_en).total_seconds()
        horas = max(0.0, delta / 3600.0)
        return round(horas, 2), "no_contactado"


def calcular_puntaje_tiempo(horas: float) -> tuple[float, str]:
    """
    Asigna el puntaje base temporal según el intervalo/bucket de horas transcurridas:
    - < 1h    = 100
    - 1-4h   = 80
    - 4-12h  = 60
    - 12-24h = 50
    - 24-48h = 30
    - > 48h  = 10

    Returns:
        tuple (puntaje_base: float, bucket: str)
    """
    if horas < 1.0:
        return 100.0, "<1h"
    elif horas < 4.0:
        return 80.0, "1-4h"
    elif horas < 12.0:
        return 60.0, "4-12h"
    elif horas < 24.0:
        return 50.0, "12-24h"
    elif horas < 48.0:
        return 30.0, "24-48h"
    else:
        return 10.0, ">48h"


def determinar_temperatura(puntaje: float) -> str:
    """
    Clasifica el puntaje de prioridad operacional en 4 categorías:
    - 0  - 24.99 : Bajo
    - 25 - 49.99 : Medio
    - 50 - 74.99 : Alto
    - 75 - 100   : Crítico
    """
    if puntaje < 25.0:
        return "Bajo"
    elif puntaje < 50.0:
        return "Medio"
    elif puntaje < 75.0:
        return "Alto"
    else:
        return "Crítico"


def normalizar_booleano_cita(val: float | str | bool | None) -> bool:
    """
    Convierte el valor de pidio_cita a booleano estricto.
    """
    if val is True:
        return True
    if isinstance(val, str):
        val_clean = val.strip().upper()
        if val_clean in ("SI", "SÍ", "TRUE", "1"):
            return True
    return False


def normalizar_booleano_cuota(val: float | str | bool | None) -> bool:
    """
    Convierte el valor de manifesto_cuota_inicial / pago_inicial a booleano estricto.
    Valores 'NO', 'NO_INFORMA', NULL, 0 -> False.
    """
    if val is True:
        return True
    if isinstance(val, (int, float, Decimal)):
        return float(val) > 0
    if isinstance(val, str):
        val_clean = val.strip().upper()
        if val_clean in ("SI", "SÍ", "TRUE", "1"):
            return True
        if val_clean in ("NO", "NO_INFORMA", "FALSE", "0", "NULL", "NONE"):
            return False
        try:
            return float(val_clean) > 0
        except ValueError:
            return False
    return False


def normalizar_metodo_pago(val: float | str | bool | None) -> tuple[bool | None, str]:
    """
    Normaliza el método de pago / forma de pago declarada.
    Returns:
        (es_credito: bool | None, etiqueta_human: str)
        - es_credito = True si el método es crédito/financiamiento
        - es_credito = False si el método es contado/efectivo
        - es_credito = None si no se informa o es desconocido
    """
    if val is None:
        return None, "NO_INFORMADO"
    if isinstance(val, str):
        v = val.strip().lower()
        if v in ("credito", "crédito", "financiamiento", "credito_bancario"):
            return True, "crédito"
        elif v in ("contado", "efectivo", "transferencia", "debito"):
            return False, "contado"
        elif v in ("no_informa", "desconocido", "null", "none", ""):
            return None, "NO_INFORMADO"
    return None, "NO_INFORMADO"


def generar_razones_rules(
    horas: float,
    bucket: str,
    puntaje_tiempo_base: float,
    peso_tiempo: float,
    aporte_tiempo: float,
    pidio_cita_val: bool,
    aporte_cita: float,
    cuota_val: bool,
    aporte_cuota: float,
    puntaje_final: float,
    temperatura: str,
) -> dict:
    """
    Genera razones explicables para el modelo Fallback Rules V1.
    """
    factores = []
    if horas < 1.0:
        factores.append("Respuesta ultra rápida (<1h)")
    elif horas < 4.0:
        factores.append("Respuesta dentro de las primeras 4 horas")
    elif horas > 48.0:
        factores.append("Espera prolongada sin contacto (>48h)")

    if pidio_cita_val:
        factores.append("Solicitó cita explícitamente (+15 pts)")
    else:
        factores.append("No ha solicitado cita")

    if cuota_val:
        factores.append("Manifestó cuota inicial (+15 pts)")
    else:
        factores.append("No ha manifestado cuota inicial")

    return {
        "modelo": "rules",
        "version": "v1.0",
        "tiempo": {
            "horas": horas,
            "bucket": bucket,
            "puntaje_base": puntaje_tiempo_base,
            "peso": peso_tiempo,
            "aporte": aporte_tiempo,
        },
        "pidio_cita": {
            "valor": pidio_cita_val,
            "aporte": aporte_cita,
        },
        "manifesto_cuota_inicial": {
            "valor": cuota_val,
            "aporte": aporte_cuota,
        },
        "factores_clave": factores,
        "puntaje_final": puntaje_final,
        "temperatura": temperatura,
    }


def calcular_puntaje_prioridad(
    horas: float,
    pidio_cita: float | str | bool | None = False,
    manifesto_cuota_inicial: float | str | bool | None = False,
) -> dict:
    """
    Calcula la prioridad V1 basada en Rules V1 (manteniendo compatibilidad 100% con tests existentes):
    - Tiempo sin contacto (70%)
    - Solicitó cita (15%)
    - Manifestó cuota inicial (15%)

    Returns:
        dict con 'puntaje_prioridad', 'temperatura', 'razones', 'modelo_scoring', 'version_scoring'
    """
    puntaje_tiempo_base, bucket = calcular_puntaje_tiempo(horas)
    peso_tiempo = 0.70
    aporte_tiempo = round(puntaje_tiempo_base * peso_tiempo, 2)

    cita_bool = normalizar_booleano_cita(pidio_cita)
    aporte_cita = 15.0 if cita_bool else 0.0

    cuota_bool = normalizar_booleano_cuota(manifesto_cuota_inicial)
    aporte_cuota = 15.0 if cuota_bool else 0.0

    total_raw = aporte_tiempo + aporte_cita + aporte_cuota
    puntaje_final = max(0.0, min(100.0, round(total_raw, 2)))

    if puntaje_final == int(puntaje_final):
        puntaje_final = float(int(puntaje_final))

    temperatura = determinar_temperatura(puntaje_final)

    razones = generar_razones_rules(
        horas=horas,
        bucket=bucket,
        puntaje_tiempo_base=puntaje_tiempo_base,
        peso_tiempo=peso_tiempo,
        aporte_tiempo=aporte_tiempo,
        pidio_cita_val=cita_bool,
        aporte_cita=aporte_cita,
        cuota_val=cuota_bool,
        aporte_cuota=aporte_cuota,
        puntaje_final=puntaje_final,
        temperatura=temperatura,
    )

    return {
        "puntaje_prioridad": puntaje_final,
        "temperatura": temperatura,
        "razones": razones,
        "modelo_scoring": "rules",
        "version_scoring": "v1.0",
    }


def calcular_puntaje_logistico(
    horas: float,
    pidio_cita: float | str | bool | None = None,
    manifesto_cuota_inicial: float | str | bool | None = None,
    metodo_pago: float | str | bool | None = None,
) -> dict:
    """
    Calcula el puntaje de prioridad con Logistic Regression V1.
    Variables:
      - log_horas: log1p(horas)
      - horas_na: 0
      - pidio_cita: 1 si cita_bool else 0
      - manifesto_cuota_inicial: 1 si cuota_bool else 0
      - pago_credito: 1 si es_credito is True else 0

    Returns:
        dict con 'puntaje_prioridad', 'temperatura', 'razones', 'modelo_scoring', 'version_scoring'
    """
    log_horas = math.log1p(max(0.0, horas))
    cita_bool = normalizar_booleano_cita(pidio_cita)
    cuota_bool = normalizar_booleano_cuota(manifesto_cuota_inicial)
    es_credito, etiqueta_pago = normalizar_metodo_pago(metodo_pago)

    pidio_cita_num = 1 if cita_bool else 0
    cuota_num = 1 if cuota_bool else 0
    credito_num = 1 if es_credito is True else 0

    # Usar paquete serializado o coeficientes directos del entrenamiento
    if LR_PACKAGE is not None:
        coefs = LR_PACKAGE["coeficients"]
        intercept = LR_PACKAGE["intercept"]
    else:
        # Coeficientes entrenados en historico_cierres.csv
        coefs = {
            "log_horas": -0.2550,
            "horas_na": 0.0,
            "pidio_cita": 0.3068,
            "manifesto_cuota_inicial": 0.4263,
            "pago_credito": -0.3749,
        }
        intercept = 0.4981

    z = (
        intercept
        + coefs.get("log_horas", -0.2550) * log_horas
        + coefs.get("pidio_cita", 0.3068) * pidio_cita_num
        + coefs.get("manifesto_cuota_inicial", 0.4263) * cuota_num
        + coefs.get("pago_credito", -0.3749) * credito_num
    )

    prob = 1.0 / (1.0 + math.exp(-z))
    # Rescalar probabilidad a puntaje 0-100
    puntaje_final = max(0.0, min(100.0, round(prob * 100.0, 2)))
    if puntaje_final == int(puntaje_final):
        puntaje_final = float(int(puntaje_final))

    temperatura = determinar_temperatura(puntaje_final)

    # Explicabilidad clara
    factores = []
    if horas < 1.0:
        factores.append("Atención prioritaria (<1h sin contacto)")
    elif horas > 48.0:
        factores.append("Desgaste de urgencia (>48h sin contacto)")

    if cita_bool:
        factores.append("Solicitud de cita detectada en conversación")
    elif pidio_cita is not None:
        factores.append("No ha solicitado cita")
    else:
        factores.append("Cita: NO INFORMADA")

    if cuota_bool:
        factores.append("Manifestó cuota inicial")
    elif manifesto_cuota_inicial is not None:
        factores.append("Sin cuota inicial registrada")
    else:
        factores.append("Cuota inicial: NO INFORMADA")

    if es_credito is True:
        factores.append("Intención de pago a crédito (requiere validación financiera)")
    elif es_credito is False:
        factores.append("Intención de pago de contado")
    else:
        factores.append("Forma de pago: NO INFORMADA")

    razones = {
        "modelo": "logistic_regression",
        "version": "v1.0",
        "tiempo": {
            "horas": horas,
            "log_horas": round(log_horas, 4),
            "z_score": round(z, 4),
        },
        "pidio_cita": "SI" if cita_bool else ("NO" if pidio_cita is not None else "NO_INFORMADO"),
        "manifesto_cuota_inicial": "SI" if cuota_bool else ("NO" if manifesto_cuota_inicial is not None else "NO_INFORMADO"),
        "forma_pago_declarada": etiqueta_pago,
        "factores_clave": factores,
        "probabilidad_raw": round(prob, 4),
        "puntaje_prioridad": puntaje_final,
        "temperatura": temperatura,
    }

    return {
        "puntaje_prioridad": puntaje_final,
        "temperatura": temperatura,
        "razones": razones,
        "modelo_scoring": "logistic_regression",
        "version_scoring": "v1.0",
    }


def evaluar_scoring_hibrido(lead_data: dict, horas: float) -> dict:
    """
    Aplica la regla de decisión híbrida:
    - Si existen variables de extracción (solicita_cita, pago_inicial o metodo_pago NO son nulos):
      Ejecuta Logistic Regression V1.
    - De lo contrario:
      Ejecuta Rules V1 (Fallback).
    """
    solicita_cita = lead_data.get("solicita_cita")
    pago_inicial = lead_data.get("pago_inicial")
    metodo_pago = lead_data.get("metodo_pago")

    # Evaluar si existen variables de extracción mínima de la conversación
    tiene_extraccion = (
        solicita_cita is not None
        or pago_inicial is not None
        or metodo_pago is not None
    )

    if tiene_extraccion:
        return calcular_puntaje_logistico(
            horas=horas,
            pidio_cita=solicita_cita,
            manifesto_cuota_inicial=pago_inicial,
            metodo_pago=metodo_pago,
        )
    else:
        return calcular_puntaje_prioridad(
            horas=horas,
            pidio_cita=solicita_cita or False,
            manifesto_cuota_inicial=pago_inicial or False,
        )


def evaluar_y_guardar_scoring_lead(
    conn: psycopg.Connection | None,
    lead_id: str,
    fecha_referencia: datetime | None = None,
) -> dict:
    """
    Coordina la lectura de datos, la decisión del modelo (LR V1 vs Rules Fallback),
    y la persistencia atómica en PostgreSQL (`core.puntajes_leads`).

    Args:
        conn: Conexión activa a PostgreSQL. Si es None, abre una conexión temporal.
        lead_id: Identificador del lead.
        fecha_referencia: Fecha/hora de cálculo (opcional, defaults to now).

    Returns:
        dict con el resultado guardado o lanza una excepción en caso de error.
    """
    def _procesar(c: psycopg.Connection) -> dict:
        lead_data = get_lead_data_for_scoring(c, lead_id)
        if not lead_data:
            raise ValueError(f"Lead {lead_id} no encontrado para scoring.")

        registrado_en = lead_data["registrado_en"]
        primer_contacto_en = lead_data["primer_contacto_en"]

        # 1. Calcular horas de espera dinámicas
        horas, tipo_contacto = calcular_horas_sin_contacto(
            registrado_en=registrado_en,
            primer_contacto_en=primer_contacto_en,
            fecha_referencia=fecha_referencia,
        )

        # 2. Determinar y ejecutar scoring híbrido
        res_score = evaluar_scoring_hibrido(lead_data, horas)

        payload_puntaje = {
            "lead_id": lead_id,
            "probabilidad_comercial": None,
            "puntaje_urgencia": None,
            "puntaje_prioridad": res_score["puntaje_prioridad"],
            "temperatura": res_score["temperatura"],
            "modelo_scoring": res_score["modelo_scoring"],
            "version_scoring": res_score["version_scoring"],
            "razones": res_score["razones"],
            "puntuado_en": fecha_referencia or datetime.now(),
        }

        # 3. Guardar en PostgreSQL dentro de una transacción atómica
        guardado = guardar_puntaje_lead_trx(c, payload_puntaje)
        return guardado

    if conn is not None:
        return _procesar(conn)
    else:
        with get_connection() as connection:
            return _procesar(connection)


# ══════════════════════════════════════════════════════════════════════════════
# SCORING V2: Integración de Señales Semánticas (Gemini) + Scoring V1
# ══════════════════════════════════════════════════════════════════════════════

PUNTOS_INTENCION = {
    "baja": 20.0,
    "media": 60.0,
    "alta": 100.0,
    "indeterminada": 50.0,
}

PUNTOS_URGENCIA = {
    "baja": 20.0,
    "media": 60.0,
    "alta": 100.0,
    "indeterminada": 50.0,
}

PUNTOS_FASE_EMBUDO = {
    "exploracion": 20.0,
    "interes": 40.0,
    "evaluacion": 60.0,
    "cotizacion": 75.0,
    "visita": 90.0,
    "compra": 100.0,
    "indeterminada": 50.0,
}


def calcular_puntaje_semantico(
    analisis: Any,
) -> tuple[float, list[str]]:
    """
    Calcula el puntaje semántico determinista (0-100) a partir del análisis de Gemini.
    
    Fórmula:
      puntaje_base = 0.50 * intención + 0.30 * urgencia + 0.20 * fase_embudo
      incrementos  = (+5 si solicita_asesor) + (+5 si solicita_cotizacion) + (+5 si solicita_cita)
      total        = clamp(puntaje_base + incrementos, 0, 100)

    Control de confianza:
      Si confianza < 0.60, las variables se tratan como 'indeterminadas' y el puntaje es 50.0.
    """
    if analisis is None:
        return 50.0, ["Sin análisis semántico: asignado valor neutro (50.0)"]

    # Soporte para dict o AnalisisSemantico Pydantic
    if hasattr(analisis, "model_dump"):
        data = analisis.model_dump()
    elif isinstance(analisis, dict):
        data = analisis
    else:
        data = {}

    confianza = float(data.get("confianza", 1.0))
    razones = []

    if confianza < 0.60:
        razones.append(f"Confianza baja ({confianza:.2f} < 0.60): señales neutralizadas a 50.0 pts")
        return 50.0, razones

    intencion = str(data.get("intencion_compra", "indeterminada")).lower()
    urgencia = str(data.get("urgencia", "indeterminada")).lower()
    fase = str(data.get("fase_embudo", "indeterminada")).lower()

    pts_intencion = PUNTOS_INTENCION.get(intencion, 50.0)
    pts_urgencia = PUNTOS_URGENCIA.get(urgencia, 50.0)
    pts_fase = PUNTOS_FASE_EMBUDO.get(fase, 50.0)

    base = (0.50 * pts_intencion) + (0.30 * pts_urgencia) + (0.20 * pts_fase)

    razones.append(f"Intención de compra: {intencion} ({pts_intencion} pts -> {0.50*pts_intencion:.1f} base)")
    razones.append(f"Urgencia: {urgencia} ({pts_urgencia} pts -> {0.30*pts_urgencia:.1f} base)")
    razones.append(f"Fase del embudo: {fase} ({pts_fase} pts -> {0.20*pts_fase:.1f} base)")

    incrementos = 0.0
    if data.get("solicita_asesor") is True:
        incrementos += 5.0
        razones.append("Solicita asesor comercial (+5 pts)")
    if data.get("solicita_cotizacion") is True:
        incrementos += 5.0
        razones.append("Solicita cotización formal (+5 pts)")
    if data.get("solicita_cita") is True:
        incrementos += 5.0
        razones.append("Solicita cita / visita (+5 pts)")

    senales = data.get("senales_compra") or []
    for s in senales:
        razones.append(f"Señal detectada: {s}")

    if data.get("objecion_principal"):
        razones.append(f"Objeción identificada: {data.get('objecion_principal')}")

    total_semantico = max(0.0, min(100.0, round(base + incrementos, 2)))
    return total_semantico, razones


def calcular_scoring_v2(
    puntaje_v1: float | dict,
    analisis_semantico: Any = None,
    modelo_extraccion: str = "gemini",
) -> dict:
    """
    Calcula Scoring V2 combinando 70% Scoring V1 y 30% Puntaje Semántico.
    
    puntaje_v2 = 0.70 * puntaje_v1 + 0.30 * puntaje_semantico
    """
    if isinstance(puntaje_v1, dict):
        v1_val = float(puntaje_v1.get("puntaje_prioridad", 50.0))
        razones_v1 = puntaje_v1.get("razones")
    else:
        v1_val = float(puntaje_v1)
        razones_v1 = None

    if analisis_semantico is not None:
        puntaje_sem, razones_sem = calcular_puntaje_semantico(analisis_semantico)
    else:
        puntaje_sem = v1_val
        razones_sem = ["Sin señales semánticas adicionales (usando base V1)"]

    puntaje_v2 = max(0.0, min(100.0, round(0.70 * v1_val + 0.30 * puntaje_sem, 2)))
    if puntaje_v2 == int(puntaje_v2):
        puntaje_v2 = float(int(puntaje_v2))

    temperatura_v2 = determinar_temperatura(puntaje_v2)

    return {
        "puntaje_v1": v1_val,
        "puntaje_semantico": puntaje_sem,
        "puntaje_v2": puntaje_v2,
        "temperatura_v2": temperatura_v2,
        "modelo_extraccion": modelo_extraccion,
        "version_scoring": "v2.0",
        "razones_semanticas": razones_sem,
        "razones_v1": razones_v1,
    }


def evaluar_y_guardar_scoring_v2_lead(
    conn: psycopg.Connection | None,
    lead_id: str,
    fecha_referencia: datetime | None = None,
    mensajes: list[dict] | None = None,
    catalogo: list[dict] | None = None,
) -> dict:
    """
    Coordina el cálculo de Scoring V2 (V1 + Análisis Semántico Gemini / Fallback Reglas)
    y la persistencia atómica e idempotente en PostgreSQL (`core.puntajes_leads`).

    Mantiene el histórico V1 marcándolo como es_actual = FALSE y crea el registro V2 con es_actual = TRUE.
    """
    def _procesar(c: psycopg.Connection) -> dict:
        lead_data = get_lead_data_for_scoring(c, lead_id)
        if not lead_data:
            raise ValueError(f"Lead {lead_id} no encontrado para scoring V2.")

        registrado_en = lead_data["registrado_en"]
        primer_contacto_en = lead_data["primer_contacto_en"]

        # 1. Calcular horas de espera
        horas, _ = calcular_horas_sin_contacto(
            registrado_en=registrado_en,
            primer_contacto_en=primer_contacto_en,
            fecha_referencia=fecha_referencia,
        )

        # 2. Calcular Scoring V1 (híbrido LR / Rules)
        res_v1 = evaluar_scoring_hibrido(lead_data, horas)

        # 3. Obtener mensajes conversacionales
        msgs = mensajes
        if msgs is None:
            try:
                from queries.leads_queries import get_mensajes_lead
                msgs = get_mensajes_lead(c, lead_id)
            except Exception:
                msgs = []

        # Asegurar que la conexión quede en estado IDLE (no INTRANS) antes de llamar a la IA
        try:
            if hasattr(c, "info") and hasattr(c.info, "transaction_status"):
                import psycopg.pq
                if c.info.transaction_status == psycopg.pq.TransactionStatus.INTRANS:
                    c.commit()
        except Exception:
            pass

        # 4. Extraer análisis semántico con Gemini (o fallback a reglas) totalmente fuera de transacción DB
        sem = None
        modelo_extraccion = "reglas"
        if msgs and len(msgs) > 0:
            from ai.gemini_extractor import analizar_conversacion
            res_ext = analizar_conversacion(mensajes=msgs, catalogo=catalogo)
            sem = res_ext.analisis_semantico
            modelo_extraccion = res_ext.modelo_extraccion
        elif lead_data.get("solicita_cita") is not None or lead_data.get("pago_inicial") is not None:
            # Fallback semántico desde datos estructurados si no hay mensajes brutos
            from ai.gemini_extractor import _crear_analisis_fallback
            sem = _crear_analisis_fallback({
                "solicita_cita": lead_data.get("solicita_cita"),
                "solicita_cotizacion": None,
                "pago_inicial": lead_data.get("pago_inicial"),
                "metodo_pago": lead_data.get("metodo_pago"),
                "intencion_declarada": lead_data.get("intencion_declarada"),
                "sku_motocicleta": None,
            })
            modelo_extraccion = "reglas"

        # 5. Calcular Scoring V2
        res_v2 = calcular_scoring_v2(
            puntaje_v1=res_v1,
            analisis_semantico=sem,
            modelo_extraccion=modelo_extraccion,
        )

        # 6. Construir estructura de razones trazable
        razones_completas = {
            "modelo": "hybrid_gemini",
            "version": "v2.0",
            "puntaje_v1": res_v2["puntaje_v1"],
            "puntaje_semantico": res_v2["puntaje_semantico"],
            "puntaje_v2": res_v2["puntaje_v2"],
            "temperatura_v2": res_v2["temperatura_v2"],
            "modelo_extraccion": res_v2["modelo_extraccion"],
            "version_extraccion": "1.0",
            "razones_v1": res_v2.get("razones_v1") or res_v1.get("razones"),
            "razones_semanticas": res_v2.get("razones_semanticas", []),
        }

        payload_puntaje = {
            "lead_id": lead_id,
            "probabilidad_comercial": None,
            "puntaje_urgencia": None,
            "puntaje_prioridad": res_v2["puntaje_v2"],
            "temperatura": res_v2["temperatura_v2"],
            "modelo_scoring": "hybrid_gemini",
            "version_scoring": "v2.0",
            "razones": razones_completas,
            "puntuado_en": fecha_referencia or datetime.now(),
        }

        # 7. Persistir atómicamente en PostgreSQL
        guardado = guardar_puntaje_v2_lead_trx(c, payload_puntaje)
        return guardado

    if conn is not None:
        return _procesar(conn)
    else:
        with get_connection() as connection:
            return _procesar(connection)
