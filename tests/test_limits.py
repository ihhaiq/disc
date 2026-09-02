from storage import JsonStore


def test_try_record_usage_reserves_capacity_atomically(monkeypatch, tmp_path):
    import limits

    monkeypatch.setattr(limits, "_data", {})
    monkeypatch.setattr(limits, "_store", JsonStore(tmp_path / "limits.json"))
    monkeypatch.setattr(limits.config, "FREE_DAILY_LIMIT", 2)
    monkeypatch.setattr(limits.config, "PREMIUM_DAILY_LIMIT", 4)

    assert limits.try_record_usage(10)
    assert limits.try_record_usage(10)
    assert not limits.try_record_usage(10)
    assert limits.get_count(10) == 2


def test_whitelisted_user_does_not_consume_daily_capacity(monkeypatch, tmp_path):
    import limits

    monkeypatch.setattr(limits, "_data", {})
    monkeypatch.setattr(limits, "_store", JsonStore(tmp_path / "limits.json"))
    limits.add_whitelist(20, "test")

    assert limits.try_record_usage(20)
    assert limits.get_count(20) == 0
