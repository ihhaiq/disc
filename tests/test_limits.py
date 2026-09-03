from storage import JsonStore


def test_whitelisted_user_does_not_reserve_daily_capacity(monkeypatch, tmp_path):
    import limits

    monkeypatch.setattr(limits, "_data", {})
    monkeypatch.setattr(limits, "_reserved_counts", {})
    monkeypatch.setattr(limits, "_store", JsonStore(tmp_path / "limits.json"))
    limits.add_whitelist(20, "test")

    assert limits.reserve_usage(20)
    assert not limits.commit_reserved_usage(20)
    assert limits.get_count(20) == 0


def test_reservation_only_charges_successful_work(monkeypatch, tmp_path):
    import limits

    monkeypatch.setattr(limits, "_data", {})
    monkeypatch.setattr(limits, "_reserved_counts", {})
    monkeypatch.setattr(limits, "_store", JsonStore(tmp_path / "limits.json"))
    monkeypatch.setattr(limits.config, "FREE_DAILY_LIMIT", 1)

    assert limits.reserve_usage(30)
    assert not limits.can_create(30)
    assert limits.get_count(30) == 0
    assert limits.release_reserved_usage(30)
    assert limits.get_count(30) == 0

    assert limits.reserve_usage(30)
    assert limits.commit_reserved_usage(30)
    assert limits.get_count(30) == 1
