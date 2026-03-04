"""FastAPI application entrypoint for Sanctified Church API."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import configure_logging, get_settings
from app.routes import payments, webhooks, media

logger = logging.getLogger(__name__)
configure_logging()

app = FastAPI(
    title="Sanctified Church API",
    description="Backend for church community platform: payments, webhooks, and secure metadata.",
    version="1.0.0",
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "sanctified-church-api"}


app.include_router(payments.router, prefix="/api", tags=["payments"])
app.include_router(webhooks.router, prefix="/api", tags=["webhooks"])
app.include_router(media.router, prefix="/api", tags=["media"])

logger.info("Sanctified Church API started")
