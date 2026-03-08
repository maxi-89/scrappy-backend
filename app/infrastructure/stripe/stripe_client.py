from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import stripe


@dataclass
class PaymentIntentResult:
    payment_intent_id: str
    client_secret: str


class IStripeClient(ABC):
    @abstractmethod
    def create_payment_intent(self, amount_usd: float, order_id: str) -> PaymentIntentResult: ...

    @abstractmethod
    def construct_event(
        self, payload: bytes, sig_header: str, webhook_secret: str
    ) -> dict[str, Any]:
        """Verify Stripe webhook signature and return the parsed event."""
        ...


class StripeClient(IStripeClient):
    def __init__(self) -> None:
        stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")

    def create_payment_intent(self, amount_usd: float, order_id: str) -> PaymentIntentResult:
        intent = stripe.PaymentIntent.create(
            amount=int(round(amount_usd * 100)),  # cents
            currency="usd",
            metadata={"order_id": order_id},
        )
        return PaymentIntentResult(
            payment_intent_id=intent["id"],
            client_secret=intent["client_secret"],
        )

    def construct_event(
        self, payload: bytes, sig_header: str, webhook_secret: str
    ) -> dict[str, Any]:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        return dict(event)
