"""Stripe and Paystack webhooks: update Supabase profile.role on successful payment."""
import hmac
import hashlib
import json
import logging
from typing import Any

import stripe
from fastapi import APIRouter, Request, HTTPException, Header
from starlette.responses import Response

from app.config import get_settings
from app.services.paystack_service import verify_transaction as paystack_verify_transaction

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/stripe-webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(None, alias="Stripe-Signature"),
) -> Response:
    """
    Handle Stripe events. Verifies signature and updates Supabase profile to
    Premium Subscriber on checkout.session.completed (subscription).
    """
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        logger.warning("STRIPE_WEBHOOK_SECRET not set; webhook disabled")
        raise HTTPException(status_code=501, detail="Webhook not configured")

    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature or "", settings.stripe_webhook_secret
        )
    except ValueError as e:
        logger.warning("Invalid webhook payload: %s", e)
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError as e:
        logger.warning("Invalid webhook signature: %s", e)
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session: Any = event["data"]["object"]
        if session.get("mode") == "subscription" and session.get("subscription"):
            user_id = (session.get("metadata") or {}).get("supabase_user_id")
            if user_id:
                await _set_profile_role_premium(user_id)
            else:
                logger.info("Checkout completed but no supabase_user_id in metadata")

    return Response(status_code=200)


@router.post("/paystack-webhook")
async def paystack_webhook(
    request: Request,
    x_paystack_signature: str | None = Header(None, alias="x-paystack-signature"),
) -> Response:
    """
    Handle Paystack events (cards + M-PESA). Verifies x-paystack-signature (HMAC SHA512),
    then on charge.success updates Supabase profile.role to premium using metadata.supabase_user_id.
    """
    settings = get_settings()
    if not settings.paystack_secret_key:
        logger.warning("PAYSTACK_SECRET_KEY not set; webhook disabled")
        raise HTTPException(status_code=501, detail="Webhook not configured")

    body = await request.body()
    signature = x_paystack_signature or ""
    expected = hmac.new(
        settings.paystack_secret_key.encode("utf-8"),
        body,
        hashlib.sha512,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        logger.warning("Paystack webhook invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        event = json.loads(body)
    except json.JSONDecodeError as e:
        logger.warning("Paystack webhook invalid JSON: %s", e)
        raise HTTPException(status_code=400, detail="Invalid payload")

    event_type = event.get("event")
    if event_type == "charge.success":
        data = event.get("data", {})
        reference = data.get("reference")
        if not reference:
            logger.warning("Paystack charge.success received without reference")
            return Response(status_code=200)

        # Never trust webhook payload blindly: verify with Paystack first.
        try:
            verified = paystack_verify_transaction(reference)
        except Exception as e:
            logger.exception("Paystack verify failed for reference=%s: %s", reference, e)
            raise HTTPException(status_code=502, detail="Payment verification failed")

        if verified.get("status") != "success":
            logger.warning(
                "Paystack verify not successful for reference=%s status=%s",
                reference,
                verified.get("status"),
            )
            return Response(status_code=200)

        metadata = verified.get("metadata") or {}
        user_id = metadata.get("supabase_user_id")
        if user_id:
            await _set_profile_role_premium(user_id)
            logger.info(
                "Paystack charge.success verified and premium set for user_id=%s reference=%s",
                user_id,
                reference,
            )
        else:
            logger.info(
                "Paystack charge.success verified but no supabase_user_id in metadata "
                "for reference=%s",
                reference,
            )

    return Response(status_code=200)


def _set_profile_role_premium_sync(user_id: str) -> None:
    """Update profiles.role to 'premium' (sync for use from sync/async)."""
    from supabase import create_client

    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    result = client.table("profiles").update({"role": "premium"}).eq("id", user_id).execute()
    logger.info("Updated profile role to premium for user_id=%s result=%s", user_id, result)


async def _set_profile_role_premium(user_id: str) -> None:
    """Update profiles.role to 'premium' for the given user."""
    import asyncio

    try:
        await asyncio.to_thread(_set_profile_role_premium_sync, user_id)
    except Exception as e:
        logger.exception("Failed to update profile role for user_id=%s: %s", user_id, e)
        raise HTTPException(status_code=500, detail="Failed to update subscription status")
