from services.ephemeral import EphemeralMessenger, ephemeral_id


def test_ephemeral_id_reads_message_id():
    assert ephemeral_id({"ephemeral_message_id": 123}) == 123
    assert ephemeral_id({}) is None
    assert ephemeral_id(None) is None


def test_ephemeral_messenger_uses_shared_pending_store():
    pending_audio = {1: {"ephemeral_message_id": 456}}
    messenger = EphemeralMessenger(pending_audio)

    assert messenger.pending_audio is pending_audio
    assert messenger.message_id(pending_audio[1]) == 456
