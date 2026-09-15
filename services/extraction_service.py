"""
services/extraction_service.py
-------------------------------
Servicio de extracción de información no estructurada a partir de mensajes.

Fase 2 - Paso 1: Detección de motocicleta basada en reglas y catálogo de PostgreSQL.
Fase 2 - Paso 2: Detección de monto de pago inicial (evitando falsos positivos).
Fase 2 - Paso 3: Extracción de señales comerciales (intención, cotización, cita).
Fase 2 - Paso 4: Extracción de método de pago (Crédito, Contado).
"""

from __future__ import annotations
import re
import unicodedata

# Mapeo de números en texto (1 a 10) para expresiones coloquiales
NUMEROS_TEXTO = {
    "un": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4,
    "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10
}

# Palabras clave asociadas a cuota/pago inicial
PALABRAS_INICIAL = [
    "inicial", "cuota inicial", "pago inicial", "entrada", "enganche"
]


def _normalizar_texto(texto: str) -> str:
    """Convierte a minúsculas y remueve acentos/diacríticos."""
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto


def _obtener_textos_usuario(messages: list[dict]) -> list[str]:
    """Extrae y normaliza las frases enviadas por el usuario."""
    textos = []
    for msg in messages:
        role = msg.get("role") or msg.get("remitente")
        if role in ("user", "cliente", "Cliente"):
            content = msg.get("content") or msg.get("texto") or ""
            if content:
                textos.append(content)
    return textos


def extract_motocicleta(messages: list[dict], catalogo: list[dict]) -> str | None:
    """
    Analiza los mensajes enviados por el usuario ('role': 'user') y detecta el SKU
    de la motocicleta de interés usando el catálogo proporcionado.
    """
    textos_raw = _obtener_textos_usuario(messages)
    if not textos_raw:
        return None

    texto_completo = _normalizar_texto(" ".join(textos_raw))

    mejor_sku = None
    mejor_score = 0

    for moto in catalogo:
        sku = moto["sku"]
        marca = _normalizar_texto(moto.get("marca") or "")
        linea = _normalizar_texto(moto.get("linea") or "")

        linea_tokens = linea.split()
        score = 0

        if linea in texto_completo:
            score = 100
        else:
            palabra_principal = linea_tokens[0] if linea_tokens else ""
            if re.search(r'\b' + re.escape(palabra_principal) + r'\b', texto_completo):
                score += 40

                numeros_linea = re.findall(r'\d+', linea)
                for num in numeros_linea:
                    if re.search(r'\b' + re.escape(num) + r'\b', texto_completo):
                        score += 30

                if marca and re.search(r'\b' + re.escape(marca) + r'\b', texto_completo):
                    score += 15

                if "fi" in linea_tokens and "fi" in texto_completo:
                    score += 20
                elif "fi" in linea_tokens and "fi" not in texto_completo:
                    score -= 10

        if score > mejor_score and score >= 50:
            mejor_score = score
            mejor_sku = sku

    return mejor_sku


def extract_pago_inicial(messages: list[dict]) -> int | None:
    """
    Analiza los mensajes del usuario para extraer el monto de pago/cuota inicial.

    Filtra rigurosamente los textos para requerir una asociación explícita con conceptos de 'inicial',
    evitando confundirlo con el precio total de la motocicleta o presupuestos generales.
    """
    textos_raw = _obtener_textos_usuario(messages)
    if not textos_raw:
        return None

    # Recorrer mensajes desde el más reciente hacia el más antiguo
    for content_raw in reversed(textos_raw):
        content_norm = _normalizar_texto(content_raw)

        # Validar si el mensaje contiene alguna palabra clave de cuota inicial
        if not any(kw in content_norm for kw in PALABRAS_INICIAL):
            continue

        # 1. Millones expresados con dígitos (ej: "3 millones", "2.5 millones", "2,5 millones")
        match_mil_num = re.search(r'(\d+(?:[.,]\d+)?)\s*millon(?:es)?', content_norm)
        if match_mil_num:
            val_str = match_mil_num.group(1).replace(',', '.')
            try:
                val = float(val_str)
                return int(val * 1_000_000)
            except ValueError:
                pass

        # 2. Millones expresados en palabras (ej: "dos millones", "tres millones")
        match_mil_word = re.search(
            r'\b(un|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\s*millon(?:es)?\b',
            content_norm
        )
        if match_mil_word:
            word = match_mil_word.group(1)
            num = NUMEROS_TEXTO.get(word)
            if num:
                return num * 1_000_000

        # 3. Monto formateado con puntos o signo de pesos (ej: "$2.500.000", "1.800.000")
        match_dots = re.search(r'\$?\s*(\d{1,3}(?:\.\d{3})+)', content_raw)
        if match_dots:
            num_str = match_dots.group(1).replace('.', '')
            try:
                return int(num_str)
            except ValueError:
                pass

        # 4. Número entero sin separadores (ej: "3000000", "1800000")
        match_plain = re.search(r'\b(\d{6,8})\b', content_raw)
        if match_plain:
            try:
                return int(match_plain.group(1))
            except ValueError:
                pass

    return None


def extract_metodo_pago(messages: list[dict]) -> str | None:
    """
    Analiza las expresiones del usuario para determinar si el método de pago deseado
    es 'Crédito', 'Contado', o None si no se especifica.
    """
    textos_raw = _obtener_textos_usuario(messages)
    if not textos_raw:
        return None

    texto_completo = _normalizar_texto(" ".join(textos_raw))

    patrones_credito = [
        "credito", "financiar", "financiacion", "cuotas", "financiarla",
        "por cuotas", "credito directo", "financiar el resto", "financiar resto",
        "cuota mensual"
    ]
    if any(p in texto_completo for p in patrones_credito):
        return "Crédito"

    patrones_contado = [
        "contado", "de contado", "efectivo", "en efectivo", "transferencia",
        "un solo pago", "al contado", "pagar de una", "pago unico"
    ]
    if any(p in texto_completo for p in patrones_contado):
        return "Contado"

    return None


def extract_intencion(messages: list[dict]) -> str | None:
    """
    Determina si la intención declarada explícita es 'Compra', 'Consulta', o None si es ambigua.
    """
    textos_raw = _obtener_textos_usuario(messages)
    if not textos_raw:
        return None

    texto_completo = _normalizar_texto(" ".join(textos_raw))

    patrones_compra = [
        "quiero comprar", "deseo comprar", "comprar una", "comprarla",
        "voy a comprar", "interesado en comprar", "interesada en comprar",
        "adquirir una", "adquirir la", "quiero adquirir", "para comprar"
    ]
    if any(p in texto_completo for p in patrones_compra):
        return "Compra"

    patrones_consulta = [
        "solo estoy averiguando", "solo averigando", "solo quiero informacion",
        "solo informacion", "conocer las opciones", "solo mirando", "mirando que motos",
        "buscando opciones", "saber que motos"
    ]
    if any(p in texto_completo for p in patrones_consulta):
        return "Consulta"

    return None


def extract_solicita_cotizacion(messages: list[dict]) -> bool:
    """
    Determina si el usuario solicita cotización o información de precio/costo.
    """
    textos_raw = _obtener_textos_usuario(messages)
    if not textos_raw:
        return False

    texto_completo = _normalizar_texto(" ".join(textos_raw))

    patrones_cotizacion = [
        "cotizar", "cotizacion", "cotizame", "cotizacon",
        "cuanto cuesta", "cuanto vale", "precio", "valor de la", "valor de una",
        "cuanto sale"
    ]
    return any(p in texto_completo for p in patrones_cotizacion)


def extract_solicita_cita(messages: list[dict]) -> bool:
    """
    Determina si el usuario solicita agendar una cita o visitar el punto de venta.
    """
    textos_raw = _obtener_textos_usuario(messages)
    if not textos_raw:
        return False

    texto_completo = _normalizar_texto(" ".join(textos_raw))

    patrones_cita = [
        "cita", "agendar", "visitar el concesionario", "visitar la agencia",
        "ir al concesionario", "ir a la agencia", "ir a ver", "pasar por el punto",
        "pasar por el concesionario", "probar la moto", "test drive", "verla en persona",
        "conocer la moto en persona"
    ]
    return any(p in texto_completo for p in patrones_cita)


def extract_conversation(messages: list[dict], catalogo: list[dict]) -> dict:
    """
    Función principal de extracción.

    Devuelve un diccionario estructurado con los datos extraídos hasta el momento.
    """
    sku = extract_motocicleta(messages, catalogo)
    pago_inicial = extract_pago_inicial(messages)
    metodo_pago = extract_metodo_pago(messages)
    intencion = extract_intencion(messages)
    solicita_cot = extract_solicita_cotizacion(messages)
    solicita_cit = extract_solicita_cita(messages)

    return {
        "sku_motocicleta": sku,
        "pago_inicial": pago_inicial,
        "metodo_pago": metodo_pago,
        "intencion_declarada": intencion,
        "objecion_principal": None,
        "solicita_cotizacion": solicita_cot,
        "solicita_cita": solicita_cit,
    }
