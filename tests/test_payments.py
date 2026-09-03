from services.payments import build_subscription_payload, validate_subscription_payment


def test_valid_subscription_payment():
    payload = build_subscription_payload(42, 123456)

    result = validate_subscription_payment(
        payload=payload,
        currency="XTR",
        amount=50,
        user_id=42,
        expected_amount=50,
    )

    assert result.valid


def test_subscription_payment_rejects_tampering():
    common = {"currency": "XTR", "amount": 50, "user_id": 42, "expected_amount": 50}

    assert not validate_subscription_payment(payload="other_42_1", **common).valid
    assert not validate_subscription_payment(payload="sub_99_1", **common).valid
    assert not validate_subscription_payment(payload="sub_42_1", **common | {"amount": 49}).valid
    assert not validate_subscription_payment(payload="sub_42_1", **common | {"currency": "USD"}).valid
