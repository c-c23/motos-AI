"""
scripts/test_gemini_real.py
---------------------------
Script de validación REAL con la API oficial de Gemini.
Obtiene la API key desde .env mediante os.getenv("GEMINI_API_KEY").
NO inserta ni modifica ningún dato en PostgreSQL ni en el sistema.
"""

import os
import sys
import json
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Asegurar path raíz del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.gemini_extractor import analizar_conversacion


def cargar_catalogo() -> list[dict]:
    """Carga el catálogo de motos si está disponible."""
    catalogo_path = Path("archivosreales/catalogo_motos.csv")
    if catalogo_path.exists():
        df = pd.read_csv(catalogo_path)
        return df.to_dict(orient="records")
    return []


def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[ERROR] GEMINI_API_KEY no encontrada en el entorno.")
        sys.exit(1)

    # Nunca imprimir la API key completa
    print(f"[OK] GEMINI_API_KEY detectada: {api_key[:6]}...{api_key[-4:]}")

    catalogo = cargar_catalogo()
    print(f"[OK] Catálogo cargado con {len(catalogo)} referencias.\n")

    casos = [
        {
            "id": "CASO 1 — ALTA INTENCIÓN / URGENCIA",
            "texto": (
                "Financiada, tengo 4 palos para la inicial.\n"
                "Claro, tengo contrato indefinido.\n"
                "¿A qué hora los puedo visitar hoy?\n"
                "Claro que sí, lo esperamos. Estamos de 8 a 6, ¿le separo la moto mientras tanto?\n"
                "Hágale pues, ya voy en camino"
            )
        },
        {
            "id": "CASO 2 — INTERÉS + OBJECIÓN FINANCIERA",
            "texto": (
                "A crédito, ¿cómo es el proceso?\n"
                "¿Y cuánto queda la cuota mensual? porque el interés está caro\n"
                "Le entiendo. ¿Le mando la cotización formal al WhatsApp para que la revise con calma?\n"
                "Sí porfa, mándemela"
            )
        },
        {
            "id": "CASO 3 — EXPLORACIÓN",
            "texto": (
                "Buenas, estoy averiguando por la Honda CB 125F Twister\n"
                "Solo estaba mirando precios"
            )
        }
    ]

    for c in casos:
        print("=" * 80)
        print(f"PROCESANDO: {c['id']}")
        print("=" * 80)
        print("TEXTO DE CONVERSACIÓN:")
        print(c["texto"])
        print("-" * 80)

        resultado = analizar_conversacion(
            mensajes=c["texto"],
            catalogo=catalogo
        )

        print(f"Mecanismo utilizado (modelo_extraccion): {resultado.modelo_extraccion}")
        print(f"Versión de extracción: {resultado.version_extraccion}")
        if resultado.error_detalle:
            print(f"Detalle error (fallback): {resultado.error_detalle}")

        print("\n--- ANÁLISIS SEMÁNTICO (GEMINI / PYDANTIC) ---")
        sem = resultado.analisis_semantico
        print(f"  • Intención de compra : {sem.intencion_compra}")
        print(f"  • Urgencia             : {sem.urgencia}")
        print(f"  • Fase del embudo      : {sem.fase_embudo}")
        print(f"  • Solicita asesor      : {sem.solicita_asesor}")
        print(f"  • Solicita cotización  : {sem.solicita_cotizacion}")
        print(f"  • Solicita cita/visita : {sem.solicita_cita}")
        print(f"  • Objeción principal   : {sem.objecion_principal}")
        print(f"  • Señales de compra    : {sem.senales_compra}")
        print(f"  • Confianza            : {sem.confianza}")

        print("\n--- VARIABLES DE ENTIDAD (EXTRACTOR) ---")
        print(f"  • SKU detectado        : {resultado.sku_motocicleta}")
        print(f"  • Método de pago       : {resultado.metodo_pago}")
        print(f"  • Pago inicial         : {resultado.pago_inicial}")
        print(f"  • Intención declarada  : {resultado.intencion_declarada}")
        print("\nJSON Estructurado Completo:")
        print(json.dumps(resultado.model_dump(), indent=2, ensure_ascii=False))
        print("\n")


if __name__ == "__main__":
    main()
