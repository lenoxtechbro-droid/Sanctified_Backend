"""Paystack API: initialize and verify transactions (cards + M-PESA)."""
import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

PAYSTACK_BASE = "https://api.paystack.co"


def initialize_transaction(
    email: str,
    amount: int,
    currency: str = "KES",
    callback_url: str | None = None,
    metadata_user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    channels: list[str] | None = None,
) -> tuple[str, str, str]:
    """
    Initialize a Paystack transaction. Supports international cards and M-PESA.
    Returns (authorization_url, access_code, reference).
    """
    settings = get_settings()
    if not settings.paystack_secret_key:
        raise ValueError("PAYSTACK_SECRET_KEY is not configured")

    payload: dict[str, Any] = {
        "email": email,
        "amount": amount,
        "currency": currency,
    }
    if callback_url:
        payload["callback_url"] = callback_url

    meta: dict[str, Any] = dict(metadata or {})
    if metadata_user_id:
        meta["supabase_user_id"] = metadata_user_id
    if meta:
        payload["metadata"] = meta

    if channels:
        payload["channels"] = channels

    with httpx.Client() as client:
        resp = client.post(
            f"{PAYSTACK_BASE}/transaction/initialize",
            json=payload,
            headers={
                "Authorization": f"Bearer {settings.paystack_secret_key}",
                "Content-Type": "application/json",
            },
            timeout=15.0,
        )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("status"):
        msg = data.get("message", "Paystack initialize failed")
        logger.warning("Paystack initialize error: %s", msg)
        raise ValueError(msg)

    d = data.get("data", {})
    authorization_url = d.get("authorization_url") or ""
    access_code = d.get("access_code") or ""
    reference = d.get("reference") or ""
    if not authorization_url:
        raise ValueError("Paystack did not return authorization_url")

    logger.info("Paystack transaction initialized reference=%s", reference)
    return authorization_url, access_code, reference


def verify_transaction(reference: str) -> dict[str, Any]:
    """
    Verify a Paystack transaction by reference.

    This wraps GET /transaction/verify/{reference} and returns the inner `data`
    object from Paystack, which includes status, amount, currency, metadata, etc.
    """
    settings = get_settings()
    if not settings.paystack_secret_key:
        raise ValueError("PAYSTACK_SECRET_KEY is not configured")

    with httpx.Client() as client:
        resp = client.get(
            f"{PAYSTACK_BASE}/transaction/verify/{reference}",
            headers={
                "Authorization": f"Bearer {settings.paystack_secret_key}",
                "Content-Type": "application/json",
            },
            timeout=15.0,
        )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("status"):
        msg = data.get("message", "Paystack verify failed")
        logger.warning("Paystack verify error: %s", msg)
        raise ValueError(msg)

    tx = data.get("data") or {}
    logger.info(
        "Paystack transaction verified reference=%s status=%s amount=%s currency=%s",
        reference,
        tx.get("status"),
        tx.get("amount"),
        tx.get("currency"),
    )
    return tx
