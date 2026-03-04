"""Stripe checkout and subscription logic."""
import logging
from typing import Optional

import stripe
from app.config import get_settings
from app.models.payments import CheckoutMode

logger = logging.getLogger(__name__)


def create_checkout_session(
    mode: CheckoutMode,
    success_url: str,
    cancel_url: str,
    customer_email: Optional[str] = None,
    metadata_user_id: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """
    Create a Stripe Checkout Session.
    Returns (checkout_url, session_id).
    """
    settings = get_settings()
    stripe.api_key = settings.stripe_secret_key

    metadata: dict = {}
    if metadata_user_id:
        metadata["supabase_user_id"] = metadata_user_id

    if mode == CheckoutMode.SUBSCRIBER:
        if not settings.stripe_price_id_subscriber:
            raise ValueError("STRIPE_PRICE_ID_SUBSCRIBER is not configured")
        session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[
                {
                    "price": settings.stripe_price_id_subscriber,
                    "quantity": 1,
                }
            ],
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=customer_email or None,
            metadata=metadata,
            subscription_data={"metadata": metadata},
        )
        logger.info("Created subscription checkout session id=%s", session.id)
        return (session.url or "", session.id)

    if mode == CheckoutMode.OFFERING:
        # One-time payment: use configured price or a default amount
        price_id = settings.stripe_price_id_offering
        if price_id:
            line_items = [{"price": price_id, "quantity": 1}]
        else:
            # No product configured: use payment_intent_data with custom amount
            line_items = [
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": "Church Offering",
                            "description": "One-time offering to Sanctified Church",
                        },
                        "unit_amount": 500,  # $5.00 in cents; make configurable if needed
                    },
                    "quantity": 1,
                }
            ]
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=line_items,
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=customer_email or None,
            metadata=metadata,
        )
        logger.info("Created offering checkout session id=%s", session.id)
        return (session.url or "", session.id)

    raise ValueError(f"Unknown checkout mode: {mode}")
