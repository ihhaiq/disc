import math

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import config
import limits
import texts as texts_module
from services.contexts import with_context_suffix
from services.localization import tr

VINYL_TEMPLATE_PREVIEW_URL = "https://t.me/VinylTemplate"
PREVIEW_EMOJI_ID = "5904219717073114606"
CHANNEL_RESULT_URL = "http://t.me/discbybot?start=help"
CHANNEL_RESULT_EMOJI = "💌"

PREMIUM_EMOJI_IDS = {
    "emerald": "5285265490350972397",
    "koi": "5339487433828353468",
    "kiss": "5474525960143385880",
    "ali": "5460737770798489825",
    "black": "5399878127163811970",
}


def build_channel_result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{CHANNEL_RESULT_EMOJI} كيف اسوي وحدة مثل هذي؟",
                    url=CHANNEL_RESULT_URL,
                    style="danger",
                )
            ]
        ]
    )


def build_buy_stars_keyboard(user_id: int = 0) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr("BTN_BUY_STARS", user_id).format(
                        price=config.STARS_SUBSCRIPTION_PRICE
                    ),
                    callback_data="buy_stars",
                )
            ]
        ]
    )


def build_customize_keyboard(
    user_id: int,
    current_rotation_seconds: float | None,
) -> InlineKeyboardMarkup:
    labels = [
        (tr("SPEED_LABEL_FULL", user_id), "full"),
        (tr("SPEED_LABEL_8RPM", user_id), "8"),
        (tr("SPEED_LABEL_19RPM", user_id), "19"),
        (tr("SPEED_LABEL_33RPM", user_id), "33"),
        (tr("SPEED_LABEL_45RPM", user_id), "45"),
    ]
    buttons = []
    for label, value in labels:
        selected = (
            current_rotation_seconds in (None, 0)
            if value == "full"
            else current_rotation_seconds == (60 / float(value))
        )
        mark = " ✅" if selected else ""
        buttons.append(
            InlineKeyboardButton(
                text=f"{label}{mark}",
                callback_data=f"speed:{value}",
                style="primary",
            )
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            buttons[:2],
            buttons[2:4],
            buttons[4:6],
            [
                InlineKeyboardButton(
                    text=tr("BTN_VINYL_COLOR_MENU", user_id),
                    callback_data="vinyl_menu:open",
                    style="danger",
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr("BTN_BACK", user_id),
                    callback_data="customize:back",
                    style="primary",
                )
            ],
        ]
    )


def build_start_keyboard(user_id: int, bot_username: str) -> InlineKeyboardMarkup:
    add_url = f"https://t.me/{bot_username}?startgroup=start"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ أضفني للمجموعة",
                    url=add_url,
                    style="primary",
                )
            ],
            [
                InlineKeyboardButton(
                    text=texts_module.BTN_LANG,
                    callback_data="lang:toggle",
                    style="success",
                ),
                InlineKeyboardButton(
                    text=tr("BTN_CUSTOMIZE", user_id),
                    callback_data="customize:open",
                    style="danger",
                ),
            ],
        ]
    )


def build_vinyl_color_keyboard(
    user_id: int = 0,
    *,
    current_choice: str | None = None,
    has_premium: bool = False,
) -> InlineKeyboardMarkup:
    def label(var_name: str, value: str) -> str:
        text = tr(var_name, user_id)
        is_selected = current_choice == value or (
            current_choice is None and value == "default"
        )
        if limits.is_premium_color(value) and not has_premium:
            text = f"🔒 {text}"
        return f"{text} ✅" if is_selected else text

    def button_style(value: str) -> str:
        is_selected = current_choice == value or (
            current_choice is None and value == "default"
        )
        return "success" if is_selected else "default"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=label("BTN_VINYL_BLACK", "default"),
                    callback_data="vinyl:default",
                    style=button_style("default"),
                    icon_custom_emoji_id=PREMIUM_EMOJI_IDS["black"],
                )
            ],
            [
                InlineKeyboardButton(
                    text=label("BTN_VINYL_PINK", "pink"),
                    callback_data="vinyl:pink",
                    style=button_style("pink"),
                ),
                InlineKeyboardButton(
                    text=label("BTN_VINYL_BLUE", "blue"),
                    callback_data="vinyl:blue",
                    style=button_style("blue"),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=label("BTN_VINYL_YELLOW", "yellow"),
                    callback_data="vinyl:yellow",
                    style=button_style("yellow"),
                ),
                InlineKeyboardButton(
                    text=label("BTN_VINYL_RED", "red"),
                    callback_data="vinyl:red",
                    style=button_style("red"),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=label("BTN_VINYL_GREEN", "green"),
                    callback_data="vinyl:green",
                    style=button_style("green"),
                ),
                InlineKeyboardButton(
                    text=label("BTN_VINYL_BLOODY", "bloody"),
                    callback_data="vinyl:bloody",
                    style=button_style("bloody"),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=label("BTN_VINYL_ROSE", "rose"),
                    callback_data="vinyl:rose",
                    style=button_style("rose"),
                )
            ],
            [
                InlineKeyboardButton(
                    text=label("BTN_VINYL_EMERALD", "emerald"),
                    callback_data="vinyl:emerald",
                    style=button_style("emerald"),
                    icon_custom_emoji_id=PREMIUM_EMOJI_IDS["emerald"],
                )
            ],
            [
                InlineKeyboardButton(
                    text=label("BTN_VINYL_KOI", "koi"),
                    callback_data="vinyl:koi",
                    style=button_style("koi"),
                    icon_custom_emoji_id=PREMIUM_EMOJI_IDS["koi"],
                ),
                InlineKeyboardButton(
                    text=label("BTN_VINYL_KISS", "kiss"),
                    callback_data="vinyl:kiss",
                    style=button_style("kiss"),
                    icon_custom_emoji_id=PREMIUM_EMOJI_IDS["kiss"],
                ),
                InlineKeyboardButton(
                    text=label("BTN_VINYL_ALI", "ali"),
                    callback_data="vinyl:ali",
                    style=button_style("ali"),
                    icon_custom_emoji_id=PREMIUM_EMOJI_IDS["ali"],
                ),
            ],
            [
                InlineKeyboardButton(
                    text=tr("BTN_VINYL_COLOR_PREVIEW", user_id),
                    url=VINYL_TEMPLATE_PREVIEW_URL,
                    icon_custom_emoji_id=PREVIEW_EMOJI_ID,
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr("BTN_BACK", user_id),
                    callback_data="vinyl_menu:back",
                )
            ],
        ]
    )


def build_mode_keyboard(
    user_id: int,
    *,
    chat_id: int | None = None,
    message_id: int | None = None,
) -> InlineKeyboardMarkup:
    def callback_data(data: str) -> str:
        return with_context_suffix(data, chat_id, message_id)

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr("BTN_QUICK_CREATE", user_id),
                    callback_data=callback_data("mode:quick"),
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr("BTN_CUSTOMIZE", user_id),
                    callback_data=callback_data("mode:custom"),
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr("BTN_CANCEL", user_id),
                    callback_data=callback_data("cancel_queue"),
                )
            ],
        ]
    )


def build_wiz_color_keyboard(
    user_id: int = 0,
    channel_chat_id: int | None = None,
    channel_message_id: int | None = None,
    *,
    has_premium: bool = False,
) -> InlineKeyboardMarkup:
    def callback_data(data: str) -> str:
        return with_context_suffix(data, channel_chat_id, channel_message_id)

    def label(var_name: str, value: str) -> str:
        text = tr(var_name, user_id)
        if limits.is_premium_color(value) and not has_premium:
            return f"🔒 {text}"
        return text

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=label("BTN_VINYL_BLACK", "default"),
                    callback_data=callback_data("wiz_color:default"),
                    style="primary",
                )
            ],
            [
                InlineKeyboardButton(
                    text=label("BTN_VINYL_PINK", "pink"),
                    callback_data=callback_data("wiz_color:pink"),
                    style="primary",
                ),
                InlineKeyboardButton(
                    text=label("BTN_VINYL_BLUE", "blue"),
                    callback_data=callback_data("wiz_color:blue"),
                    style="primary",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=label("BTN_VINYL_YELLOW", "yellow"),
                    callback_data=callback_data("wiz_color:yellow"),
                    style="primary",
                ),
                InlineKeyboardButton(
                    text=label("BTN_VINYL_RED", "red"),
                    callback_data=callback_data("wiz_color:red"),
                    style="primary",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=label("BTN_VINYL_GREEN", "green"),
                    callback_data=callback_data("wiz_color:green"),
                    style="primary",
                ),
                InlineKeyboardButton(
                    text=label("BTN_VINYL_BLOODY", "bloody"),
                    callback_data=callback_data("wiz_color:bloody"),
                    style="primary",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=label("BTN_VINYL_EMERALD", "emerald"),
                    callback_data=callback_data("wiz_color:emerald"),
                    style="primary",
                    icon_custom_emoji_id=PREMIUM_EMOJI_IDS["emerald"],
                )
            ],
            [
                InlineKeyboardButton(
                    text=label("BTN_VINYL_ROSE", "rose"),
                    callback_data=callback_data("wiz_color:rose"),
                    style="primary",
                )
            ],
            [
                InlineKeyboardButton(
                    text=label("BTN_VINYL_KOI", "koi"),
                    callback_data=callback_data("wiz_color:koi"),
                    style="primary",
                    icon_custom_emoji_id=PREMIUM_EMOJI_IDS["koi"],
                ),
                InlineKeyboardButton(
                    text=label("BTN_VINYL_KISS", "kiss"),
                    callback_data=callback_data("wiz_color:kiss"),
                    style="primary",
                    icon_custom_emoji_id=PREMIUM_EMOJI_IDS["kiss"],
                ),
            ],
            [
                InlineKeyboardButton(
                    text=label("BTN_VINYL_ALI", "ali"),
                    callback_data=callback_data("wiz_color:ali"),
                    style="primary",
                    icon_custom_emoji_id=PREMIUM_EMOJI_IDS["ali"],
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr("BTN_VINYL_COLOR_PREVIEW", user_id),
                    url=VINYL_TEMPLATE_PREVIEW_URL,
                    icon_custom_emoji_id=PREVIEW_EMOJI_ID,
                )
            ],
        ]
    )


def build_wiz_speed_keyboard(
    user_id: int = 0,
    channel_chat_id: int | None = None,
    channel_message_id: int | None = None,
) -> InlineKeyboardMarkup:
    labels = [
        (tr("SPEED_LABEL_FULL", user_id), "full"),
        (tr("SPEED_LABEL_8RPM", user_id), "8"),
        (tr("SPEED_LABEL_19RPM", user_id), "19"),
        (tr("SPEED_LABEL_33RPM", user_id), "33"),
        (tr("SPEED_LABEL_45RPM", user_id), "45"),
    ]
    buttons = [
        InlineKeyboardButton(
            text=label,
            callback_data=with_context_suffix(
                f"wiz_speed:{value}", channel_chat_id, channel_message_id
            ),
        )
        for label, value in labels
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[buttons[:2], buttons[2:4], buttons[4:6]]
    )


def build_wiz_image_keyboard(
    has_thumbnail: bool,
    user_id: int = 0,
    channel_chat_id: int | None = None,
    channel_message_id: int | None = None,
) -> InlineKeyboardMarkup:
    rows = []
    if has_thumbnail:
        rows.append(
            [
                InlineKeyboardButton(
                    text=tr("BTN_WIZ_SKIP_IMAGE", user_id),
                    callback_data=with_context_suffix(
                        "wiz_image:skip", channel_chat_id, channel_message_id
                    ),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=tr("BTN_CANCEL", user_id),
                callback_data=with_context_suffix(
                    "cancel_queue", channel_chat_id, channel_message_id
                ),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_wiz_segment_keyboard(
    total_duration: float,
    user_id: int = 0,
    channel_chat_id: int | None = None,
    channel_message_id: int | None = None,
) -> InlineKeyboardMarkup:
    minutes_count = max(1, math.ceil(total_duration / 60))
    buttons = []
    for i in range(minutes_count):
        start = i * 60
        if start >= total_duration:
            break
        buttons.append(
            InlineKeyboardButton(
                text=tr("BTN_WIZ_SEGMENT_FMT", user_id).format(n=i + 1),
                callback_data=with_context_suffix(
                    f"wiz_segment:{start}", channel_chat_id, channel_message_id
                ),
                style="success",
            )
        )
    rows = [buttons[i : i + 3] for i in range(0, len(buttons), 3)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_wiz_confirm_keyboard(user_id: int = 0) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr("BTN_WIZ_PREVIEW", user_id),
                    callback_data="wiz_preview_confirm",
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr("BTN_WIZ_CONFIRM_FULL", user_id),
                    callback_data="wiz_full_confirm",
                    style="success",
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr("BTN_CANCEL", user_id),
                    callback_data="cancel_queue",
                )
            ],
        ]
    )
