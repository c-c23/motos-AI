from fastapi import FastAPI
from api.telegram import router as telegram_router

app = FastAPI(
    title="Motos AI Leads API",
    version="1.0.0",
    description="API de integración para recepción y persistencia de leads."
)

app.include_router(telegram_router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}