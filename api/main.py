from fastapi import FastAPI
from database import get_connection
from api.telegram import router as telegram_router


app = FastAPI(
    title="Motos AI Leads API",
    version="1.0.0",
    description="API de integración para recepción y persistencia de leads.",
)


app.include_router(
    telegram_router,
    prefix="/api/v1",
)


@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/health/db")
def health_db():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database();")
            database = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(*)
                FROM core.leads;
            """)
            total_leads = cur.fetchone()[0]

            cur.execute("""
                SELECT lead_id
                FROM core.leads
                ORDER BY registrado_en DESC
                LIMIT 1;
            """)
            ultimo_lead = cur.fetchone()

    return {
        "status": "ok",
        "database": database,
        "total_leads": total_leads,
        "ultimo_lead": ultimo_lead[0] if ultimo_lead else None,
    }