from storage import JsonStore


def test_help_draft_and_publish_round_trip(monkeypatch, tmp_path):
    import help_storage

    monkeypatch.setattr(help_storage, "_store", JsonStore(tmp_path / "help.json"))
    draft = {"html": "<b>Help</b>", "blocks": None, "buttons": []}

    help_storage.save_draft(7, draft)
    assert help_storage.get_draft(7) == draft

    help_storage.publish(7, draft, editor_name="Dev")
    published = help_storage.get_published()
    assert published is not None
    assert published["html"] == "<b>Help</b>"
    assert published["editor_id"] == 7
