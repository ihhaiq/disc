from __future__ import annotations

import ast
import re
from pathlib import Path

HANDLERS = Path("handlers.py")
KEYBOARD = Path("keyboard.py")

BUTTON_BUILDERS = {
    "build_buy_stars_keyboard",
    "build_customize_keyboard",
    "build_start_keyboard",
    "build_vinyl_color_keyboard",
    "build_wiz_color_keyboard",
    "build_wiz_speed_keyboard",
    "build_wiz_image_keyboard",
    "build_wiz_segment_keyboard",
    "build_wiz_confirm_keyboard",
}


def remove_top_level_functions(source: str, names: set[str]) -> str:
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    spans: list[tuple[int, int]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            start = node.lineno - 1
            end = node.end_lineno or node.lineno
            while end < len(lines) and not lines[end].strip():
                end += 1
            spans.append((start, end))
    missing = names - {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names
    }
    if missing:
        raise RuntimeError(f"Missing keyboard builders in handlers.py: {sorted(missing)}")
    for start, end in sorted(spans, reverse=True):
        del lines[start:end]
    return "".join(lines)


def replace_once(source: str, pattern: str, replacement: str, *, flags: int = 0) -> str:
    updated, count = re.subn(pattern, replacement, source, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"Expected one replacement for pattern: {pattern!r}; got {count}")
    return updated


def update_keyboard() -> None:
    source = KEYBOARD.read_text(encoding="utf-8")
    if "CHANNEL_RESULT_URL" not in source:
        anchor = 'PREVIEW_EMOJI_ID = "5904219717073114606"\n'
        addition = (
            anchor
            + '\nCHANNEL_RESULT_URL = "http://t.me/discbybot?start=help"\n'
            + 'CHANNEL_RESULT_EMOJI = "💌"\n'
        )
        source = source.replace(anchor, addition, 1)

    if "def build_channel_result_keyboard" not in source:
        marker = "\n\ndef build_buy_stars_keyboard"
        function = '''\n\ndef build_channel_result_keyboard() -> InlineKeyboardMarkup:\n    return InlineKeyboardMarkup(\n        inline_keyboard=[\n            [\n                InlineKeyboardButton(\n                    text=f"{CHANNEL_RESULT_EMOJI} كيف اسوي وحدة مثل هذي؟",\n                    url=CHANNEL_RESULT_URL,\n                    style="danger",\n                )\n            ]\n        ]\n    )\n'''
        source = source.replace(marker, function + marker, 1)

    ast.parse(source)
    KEYBOARD.write_text(source, encoding="utf-8")


def update_handlers() -> None:
    source = HANDLERS.read_text(encoding="utf-8")
    source = remove_top_level_functions(source, BUTTON_BUILDERS)

    source = source.replace("    InlineKeyboardButton,\n", "")
    if "import keyboard as keyboards\n" not in source:
        source = source.replace(
            "from compose import build_disc\n",
            "from compose import build_disc\nimport keyboard as keyboards\n",
            1,
        )

    source = re.sub(
        r'\nVINYL_TEMPLATE_PREVIEW_URL = "https://t\.me/VinylTemplate"\nPREVIEW_EMOJI_ID = "5904219717073114606"\n\n\nPREMIUM_EMOJI_IDS = \{.*?\}\n',
        "\n",
        source,
        count=1,
        flags=re.S,
    )

    source = replace_once(
        source,
        r'(pending_audio\[key\] = \{.*?\n    \}\n    wizard_state\.pop\(key, None\)\n)\n    keyboard = InlineKeyboardMarkup\(.*?\n    \)\n\n    try:',
        r'\1\n    keyboard = keyboards.build_mode_keyboard(\n        key, chat_id=chat_id, message_id=message.message_id\n    )\n\n    try:',
        flags=re.S,
    )

    source = replace_once(
        source,
        r'(pending_images\.pop\(uid, None\)\n)\n    keyboard = InlineKeyboardMarkup\(.*?\n    \)\n    if is_group:',
        r'\1\n    keyboard = keyboards.build_mode_keyboard(owner_id)\n    if is_group:',
        flags=re.S,
    )

    source = replace_once(
        source,
        r'(    if is_group:\n)        group_keyboard = InlineKeyboardMarkup\(.*?\n        \)\n        sent = await send_ephemeral_text\(',
        r'\1        group_keyboard = keyboards.build_mode_keyboard(\n            owner_id, chat_id=message.chat.id, message_id=message.message_id\n        )\n        sent = await send_ephemeral_text(',
        flags=re.S,
    )

    source = replace_once(
        source,
        r'        final_keyboard = None\n        if _is_shared_context\(context_key\):\n            final_keyboard = InlineKeyboardMarkup\(.*?\n            \)\n\n        try:',
        '        final_keyboard = (\n            keyboards.build_channel_result_keyboard()\n            if _is_shared_context(context_key)\n            else None\n        )\n\n        try:',
        flags=re.S,
    )

    replacements = {
        "build_buy_stars_keyboard": "keyboards.build_buy_stars_keyboard",
        "build_start_keyboard": "keyboards.build_start_keyboard",
        "build_wiz_speed_keyboard": "keyboards.build_wiz_speed_keyboard",
        "build_wiz_image_keyboard": "keyboards.build_wiz_image_keyboard",
        "build_wiz_segment_keyboard": "keyboards.build_wiz_segment_keyboard",
        "build_wiz_confirm_keyboard": "keyboards.build_wiz_confirm_keyboard",
        "build_customize_keyboard": "_customize_keyboard",
        "build_vinyl_color_keyboard": "_vinyl_color_keyboard",
        "build_wiz_color_keyboard": "_wiz_color_keyboard",
    }
    for old, new in replacements.items():
        source = re.sub(rf"(?<![\w.]){old}\b", new, source)

    helper_anchor = "\ndef get_job_priority(user_id: int) -> int:\n"
    helpers = '''\n\ndef _customize_keyboard(user_id: int) -> InlineKeyboardMarkup:\n    return keyboards.build_customize_keyboard(\n        user_id, get_user_rotation_seconds(user_id)\n    )\n\n\ndef _vinyl_color_keyboard(user_id: int = 0) -> InlineKeyboardMarkup:\n    return keyboards.build_vinyl_color_keyboard(\n        user_id,\n        current_choice=developer_vinyl_choice.get(user_id),\n        has_premium=user_has_premium_access(user_id),\n    )\n\n\ndef _wiz_color_keyboard(\n    user_id: int = 0,\n    channel_chat_id: int | None = None,\n    channel_message_id: int | None = None,\n) -> InlineKeyboardMarkup:\n    return keyboards.build_wiz_color_keyboard(\n        user_id,\n        channel_chat_id,\n        channel_message_id,\n        has_premium=user_has_premium_access(user_id),\n    )\n'''
    if "def _customize_keyboard" not in source:
        source = source.replace(helper_anchor, helpers + helper_anchor, 1)

    # The suffix helper is now owned by keyboard.py; handlers only parses suffixes.
    source = source.replace(
        "from services.contexts import with_context_suffix as _with_channel_suffix\n", ""
    )

    tree = ast.parse(source)
    remaining_builders = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in BUTTON_BUILDERS
    }
    if remaining_builders:
        raise RuntimeError(f"Keyboard builders still in handlers.py: {sorted(remaining_builders)}")
    if "InlineKeyboardButton" in source:
        raise RuntimeError("InlineKeyboardButton is still present in handlers.py")
    if "InlineKeyboardMarkup(" in source:
        raise RuntimeError("InlineKeyboardMarkup construction is still present in handlers.py")

    HANDLERS.write_text(source, encoding="utf-8")


if __name__ == "__main__":
    update_keyboard()
    update_handlers()
    print("keyboard extraction completed")
