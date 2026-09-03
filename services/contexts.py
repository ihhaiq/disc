"""Context identifiers shared by private, group, and channel flows."""

CHANNEL_KEY_PREFIX = "c"
GROUP_KEY_PREFIX = "g"


def channel_key(chat_id: int, message_id: int) -> str:
    return f"{CHANNEL_KEY_PREFIX}{chat_id}:{message_id}"


def group_key(chat_id: int, message_id: int) -> str:
    return f"{GROUP_KEY_PREFIX}{chat_id}:{message_id}"


def is_channel_context(uid: object) -> bool:
    return isinstance(uid, str) and uid.startswith(CHANNEL_KEY_PREFIX)


def is_group_context(uid: object) -> bool:
    return isinstance(uid, str) and uid.startswith(GROUP_KEY_PREFIX)


def is_shared_context(uid: object) -> bool:
    return is_channel_context(uid) or is_group_context(uid)


def with_context_suffix(
    callback_data: str,
    chat_id: int | None,
    message_id: int | None,
) -> str:
    if chat_id is None or message_id is None:
        return callback_data
    return f"{callback_data}:{chat_id}:{message_id}"


def split_context_suffix(data: str) -> tuple[str, int | None, int | None]:
    parts = data.split(":")
    if len(parts) >= 3:
        maybe_chat, maybe_message = parts[-2], parts[-1]
        if maybe_chat.lstrip("-").isdigit() and maybe_message.isdigit():
            return ":".join(parts[:-2]), int(maybe_chat), int(maybe_message)
    return data, None, None
