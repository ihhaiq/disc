from services.contexts import (
    channel_key,
    group_key,
    is_channel_context,
    is_group_context,
    is_shared_context,
    split_context_suffix,
    with_context_suffix,
)


def test_context_keys_do_not_overlap():
    channel = channel_key(-100, 5)
    group = group_key(-100, 5)

    assert channel != group
    assert is_channel_context(channel)
    assert is_group_context(group)
    assert is_shared_context(channel)
    assert not is_shared_context(10)


def test_callback_context_suffix_round_trip():
    value = with_context_suffix("mode:quick", -100123, 44)

    assert split_context_suffix(value) == ("mode:quick", -100123, 44)
    assert split_context_suffix("mode:quick") == ("mode:quick", None, None)
