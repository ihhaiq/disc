"""Validation helpers for Telegram Stars payments."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PaymentCheck:
    valid: bool
    reason: str = ""


def build_subscription_payload(user_id: int, timestamp: int) -> str:
    return f"sub_{user_id}_{timestamp}"


def validate_subscription_payment(
    *,
    payload: str,
    currency: str,
    amount: int,
    user_id: int,
    expected_amount: int,
) -> PaymentCheck:
    parts = payload.split("_")
    if len(parts) != 3 or parts[0] != "sub":
        return PaymentCheck(False, "invalid payload")
    try:
        payload_user_id = int(parts[1])
        timestamp = int(parts[2])
    except ValueError:
        return PaymentCheck(False, "invalid payload values")
    if payload_user_id != user_id or timestamp <= 0:
        return PaymentCheck(False, "payload does not belong to user")
    if currency != "XTR":
        return PaymentCheck(False, "invalid currency")
    if amount != expected_amount:
        return PaymentCheck(False, "invalid amount")
    return PaymentCheck(True)
