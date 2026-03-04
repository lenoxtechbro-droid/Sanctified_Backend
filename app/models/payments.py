"""Request/response models for payment endpoints."""
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class CheckoutMode(str, Enum):
    """Checkout session type."""
    OFFERING = "offering"       # One-time church offering
    SUBSCRIBER = "subscriber"   # Monthly premium subscription


class CreateCheckoutSessionRequest(BaseModel):
    """Body for POST /create-checkout-session."""
    mode: CheckoutMode = Field(..., description="offering or subscriber")
    success_url: str = Field(..., description="Frontend URL after success")
    cancel_url: str = Field(..., description="Frontend URL if user cancels")
    customer_email: Optional[str] = Field(None, description="Pre-fill Stripe checkout email")
    metadata_user_id: Optional[str] = Field(None, description="Supabase user id for webhook to update profile")


class CreateCheckoutSessionResponse(BaseModel):
    """Response with Stripe Checkout URL."""
    url: str = Field(..., description="Redirect user to this URL for payment")
    session_id: Optional[str] = Field(
        None, description="Stripe session id for client tracking"
    )


class DonationPaymentMethod(str, Enum):
    """Supported donation payment methods (mapped to Paystack channels)."""

    MPESA = "mpesa"
    CARD = "card"


class InitializeDonationPaymentRequest(BaseModel):
    """
    Body for POST /api/initialize-payment (Giving & Offerings).

    This is a thin wrapper around Paystack initialize, so we keep it simple
    and let Paystack handle the heavy lifting (cards + M-PESA).
    """

    user_id: str = Field(..., description="Supabase auth user id")
    email: str = Field(..., description="Donor email (for Paystack customer)")
    amount: int = Field(..., gt=0, description="Amount in whole currency units (e.g. 500 KES)")
    currency: Literal["KES", "NGN", "GHS", "USD"] = Field(
        "KES", description="Currency code; Paystack supports KES, NGN, GHS, USD"
    )
    category: str = Field(
        ..., description="Giving category (e.g. Tithe, Offering, Thanksgiving, Building Fund)"
    )
    payment_method: DonationPaymentMethod = Field(
        ..., description="mpesa (mobile money) or card"
    )
    phone: Optional[str] = Field(
        None,
        description="Optional donor phone number; stored in metadata for reconciliation",
    )
    reference_hint: Optional[str] = Field(
        None,
        description="Optional human-friendly hint (e.g. 'Sunday service 9am') stored in metadata",
    )


class InitializeDonationPaymentResponse(BaseModel):
    """Response for POST /api/initialize-payment."""

    payment_method: DonationPaymentMethod = Field(
        ..., description="Echoed payment method (mpesa or card)"
    )
    reference: str = Field(..., description="Paystack transaction reference")
    status: Literal["pending", "success", "failed"] = Field(
        "pending",
        description="High-level donation status; starts as pending until webhook/verification",
    )
    authorization_url: Optional[str] = Field(
        None,
        description="Redirect donor to this URL to complete Paystack payment (cards or M-PESA)",
    )
    message: Optional[str] = Field(
        None,
        description="Optional display message for the frontend",
    )
