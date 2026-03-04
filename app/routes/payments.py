"""Payment API: Stripe Checkout and Paystack initialize (cards + M-PESA)."""
import logging

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.models.payments import (
    CreateCheckoutSessionRequest,
    CreateCheckoutSessionResponse,
    DonationPaymentMethod,
    InitializeDonationPaymentRequest,
    InitializeDonationPaymentResponse,
)
from app.models.paystack import (
    InitializeTransactionRequest,
    InitializeTransactionResponse,
)
from app.services.paystack_service import initialize_transaction as paystack_initialize
from app.services.stripe_service import create_checkout_session

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/create-checkout-session",
    response_model=CreateCheckoutSessionResponse,
)
def post_create_checkout_session(body: CreateCheckoutSessionRequest) -> JSONResponse:
    """
    Create a Stripe Checkout Session for offering (one-time) or subscriber (subscription).
    Frontend should redirect the user to the returned URL.
    """
    try:
        url, session_id = create_checkout_session(
            mode=body.mode,
            success_url=body.success_url,
            cancel_url=body.cancel_url,
            customer_email=body.customer_email,
            metadata_user_id=body.metadata_user_id,
        )
    except ValueError as e:
        logger.warning("Checkout session validation error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Stripe checkout session creation failed: %s", e)
        raise HTTPException(status_code=500, detail="Payment session could not be created")

    return JSONResponse(
        content=CreateCheckoutSessionResponse(url=url, session_id=session_id).model_dump()
    )


@router.post(
    "/initialize-payment",
    response_model=InitializeDonationPaymentResponse,
)
def post_initialize_donation_payment(
    body: InitializeDonationPaymentRequest,
) -> JSONResponse:
    """
    Initialize a donation payment via Paystack (cards + M-PESA).

    This wraps Paystack `/transaction/initialize`, converting the amount to subunits and
    attaching basic metadata for reconciliation. It does **not** grant Premium access;
    for subscriptions, use Stripe Checkout or call /api/paystack/initialize with
    metadata_user_id from the Checkout flow.
    """
    settings = get_settings()

    try:
        # Paystack expects subunits (e.g. KES 1 = 100); keep it simple and
        # apply the same factor for supported currencies.
        amount_subunits = body.amount * 100

        # Map our high-level payment_method to Paystack channels.
        channels: list[str] | None
        if body.payment_method == DonationPaymentMethod.MPESA:
            # Paystack will present M-PESA as mobile money where supported.
            channels = ["mobile_money"]
        elif body.payment_method == DonationPaymentMethod.CARD:
            channels = ["card"]
        else:
            raise ValueError("Unsupported payment method")

        metadata: dict[str, object] = {
            "kind": "donation",
            "category": body.category,
            "payment_method": body.payment_method.value,
            "supabase_user_id_raw": body.user_id,
        }
        if body.reference_hint:
            metadata["reference_hint"] = body.reference_hint
        if body.phone:
            metadata["phone"] = body.phone

        # Redirect back to the frontend after Paystack completes.
        callback_url = f"{settings.frontend_url}/?giving=success"

        auth_url, access_code, reference = paystack_initialize(
            email=body.email,
            amount=amount_subunits,
            currency=body.currency,
            callback_url=callback_url,
            # For donations we do NOT pass metadata_user_id, so the webhook
            # doesn't automatically grant Premium.
            metadata_user_id=None,
            metadata=metadata,
            channels=channels,
        )
    except ValueError as e:
        logger.warning("Donation initialize validation error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPStatusError as e:
        logger.exception("Donation Paystack API error: %s", e)
        raise HTTPException(status_code=502, detail="Payment provider error")
    except Exception as e:
        logger.exception("Donation initialize failed: %s", e)
        raise HTTPException(status_code=500, detail="Could not initialize payment")

    return JSONResponse(
        content=InitializeDonationPaymentResponse(
            payment_method=body.payment_method,
            reference=reference,
            status="pending",
            authorization_url=auth_url,
            message="Redirecting to Paystack to complete your giving.",
        ).model_dump()
    )


@router.post(
    "/paystack/initialize",
    response_model=InitializeTransactionResponse,
)
def post_paystack_initialize(body: InitializeTransactionRequest) -> JSONResponse:
    """
    Initialize a Paystack transaction (international cards + M-PESA).
    Redirect the user to authorization_url to complete payment.
    Include metadata_user_id so the webhook can set profile.role = premium on success.
    """
    try:
        auth_url, access_code, reference = paystack_initialize(
            email=body.email,
            amount=body.amount,
            currency=body.currency,
            callback_url=body.callback_url,
            metadata_user_id=body.metadata_user_id,
            metadata=body.metadata,
            channels=body.channels,
        )
    except ValueError as e:
        logger.warning("Paystack initialize validation error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPStatusError as e:
        logger.exception("Paystack API error: %s", e)
        raise HTTPException(status_code=502, detail="Payment provider error")
    except Exception as e:
        logger.exception("Paystack initialize failed: %s", e)
        raise HTTPException(status_code=500, detail="Could not initialize payment")

    return JSONResponse(
        content=InitializeTransactionResponse(
            authorization_url=auth_url,
            access_code=access_code,
            reference=reference,
        ).model_dump()
    )
