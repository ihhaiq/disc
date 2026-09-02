from storage import JsonStore


def test_json_store_round_trip_and_update(tmp_path):
    path = tmp_path / "nested" / "data.json"
    store = JsonStore(path)

    assert store.read({"fresh": True}) == {"fresh": True}
    assert store.write({"count": 1, "text": "عربي"})

    result = store.update(lambda data: data.update(count=data["count"] + 1) or data["count"])

    assert result == 2
    assert store.read() == {"count": 2, "text": "عربي"}
    assert not path.with_name("data.json.tmp").exists()


def test_json_store_recovers_from_invalid_root(tmp_path):
    path = tmp_path / "data.json"
    path.write_text("[]", encoding="utf-8")

    assert JsonStore(path).read({"safe": True}) == {"safe": True}
