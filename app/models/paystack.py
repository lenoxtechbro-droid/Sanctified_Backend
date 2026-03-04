"""Request/response models for Paystack payment endpoints."""
from typing import Any, Optional

from pydantic import BaseModel, Field


class InitializeTransactionRequest(BaseModel):
    """Body for POST /api/paystack/initialize."""
    email: str = Field(..., description="Customer email")
    amount: int = Field(..., description="Amount in subunits (e.g. cents, kobo, pesewas)")
    currency: str = Field("KES", description="Currency code (e.g. KES, NGN, GHS, USD)")
    callback_url: Optional[str] = Field(None, description="URL to redirect after payment")
    metadata_user_id: Optional[str] = Field(None, description="Supabase user id; webhook sets role=premium on success")
    metadata: Optional[dict[str, Any]] = Field(None, description="Extra metadata to attach to transaction")
    channels: Optional[list[str]] = Field(
        None,
        description="Payment channels: card, mobile_money, bank, ussd, qr, bank_transfer",
    )


class InitializeTransactionResponse(BaseModel):
    """Response with Paystack authorization URL and reference."""
    authorization_url: str = Field(..., description="Redirect user here to complete payment")
    access_code: str = Field(..., description="Paystack access code for this transaction")
    reference: str = Field(..., description="Transaction reference for verification")
