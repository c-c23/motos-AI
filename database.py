"""
database.py
-----------
Módulo de conexión a PostgreSQL usando psycopg y python-dotenv.

Uso:
    from database import get_connection

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM core.vw_leads_gestion;")
            print(cur.fetchone()[0])
"""

import os
import psycopg
from dotenv import load_dotenv

load_dotenv()


def get_connection() -> psycopg.Connection:
    """
    Devuelve una conexión activa a PostgreSQL.

    Lee las credenciales desde las variables de entorno:
        DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

    Raises:
        ValueError: si alguna variable de entorno requerida no está configurada.
        psycopg.OperationalError: si la conexión a la base de datos falla.
    """
    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [var for var in required if not os.getenv(var)]
    if missing:
        raise ValueError(
            f"Variables de entorno faltantes en .env: {', '.join(missing)}"
        )

    return psycopg.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )


def test_connection() -> str:
    """
    Prueba la conexión y devuelve la versión de PostgreSQL.
    Útil para diagnóstico rápido.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            return cur.fetchone()[0]


if __name__ == "__main__":
    version = test_connection()
    print("OK - Conexion exitosa")
    print(f"   {version}")
