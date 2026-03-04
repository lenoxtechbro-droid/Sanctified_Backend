"""Application configuration and environment variables."""
import logging
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Load from environment. See README for required vars."""

    # Stripe (optional; kept for backward compatibility)
    stripe_secret_key: str = ""
    stripe_webhook_secret: Optional[str] = None
    stripe_price_id_subscriber: Optional[str] = None
    stripe_price_id_offering: Optional[str] = None

    # Paystack (supports Intl cards + M-PESA)
    paystack_secret_key: str = ""

    # Supabase
    supabase_url: str = ""
    supabase_service_role_key: str = ""  # Server-side only; never expose to frontend

    # Supabase Storage (admin uploads)
    supabase_media_bucket: str = "media"
    supabase_media_public: bool = True
    supabase_media_signed_url_ttl_seconds: int = 60 * 60  # 1 hour

    # App
    app_env: str = "development"
    frontend_url: str = "http://localhost:5173"
    admin_api_key: str = ""  # Protect admin-only endpoints (send as X-Admin-Key)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


def get_settings() -> Settings:
    return Settings()


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
