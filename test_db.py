import psycopg

conn = psycopg.connect(
    host="localhost",
    port=5432,
    dbname="motos_database",
    user="postgres",
    password="1212"
)

print("Conexión exitosa")

with conn.cursor() as cur:
    cur.execute("""
        SELECT *
        FROM core.advisers
        LIMIT 3;
    """)

    rows = cur.fetchall()

    print("\nPrimeros 3 asesores:")
    for row in rows:
        print(row)

conn.close()