import math

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import config
import limits
import texts as texts_module
from services.contexts import with_context_suffix
from services.localization import tr
from vinyl_catalog import VinylStyle, get_vinyl_style_rows

VINYL_TEMPLATE_PREVIEW_URL = "https://t.me/VinylTemplate"
PREVIEW_EMOJI_ID = "5904219717073114606"
CHANNEL_RESULT_URL = "http://t.me/discbybot?start=help"
CHANNEL_RESULT_EMOJI = "💌"


def _is_selected(style: VinylStyle, current_choice: str | None) -> bool:
    return current_choice == style.key or (
        current_choice is None and style.key == "default"
    )


def _vinyl_label(
    style: VinylStyle,
    user_id: int = 0,
    *,
    current_choice: str | None = None,
    has_premium: bool = False,
    show_selected: bool = False,
) -> str:
    text = tr(style.text_key, user_id)
    if limits.is_premium_color(style.key) and not has_premium:
        text = f"🔒 {text}"
    if show_selected and _is_selected(style, current_choice):
        text = f"{text} ✅"
    return text


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
    rows = []
    for style_row in get_vinyl_style_rows():
        rows.append(
            [
                InlineKeyboardButton(
                    text=_vinyl_label(
                        style,
                        user_id,
                        current_choice=current_choice,
                        has_premium=has_premium,
                        show_selected=True,
                    ),
                    callback_data=f"vinyl:{style.key}",
                    style="success" if _is_selected(style, current_choice) else "default",
                    icon_custom_emoji_id=style.icon_custom_emoji_id,
                )
                for style in style_row
            ]
        )

    rows.extend(
        [
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
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
    rows = []
    for style_row in get_vinyl_style_rows():
        rows.append(
            [
                InlineKeyboardButton(
                    text=_vinyl_label(
                        style,
                        user_id,
                        has_premium=has_premium,
                    ),
                    callback_data=with_context_suffix(
                        f"wiz_color:{style.key}",
                        channel_chat_id,
                        channel_message_id,
                    ),
                    style="primary",
                    icon_custom_emoji_id=style.icon_custom_emoji_id,
                )
                for style in style_row
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text=tr("BTN_VINYL_COLOR_PREVIEW", user_id),
                url=VINYL_TEMPLATE_PREVIEW_URL,
                icon_custom_emoji_id=PREVIEW_EMOJI_ID,
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


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


def build_dev_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=getattr(texts_module, style.text_key, style.key),
                callback_data=f"vinyl:{style.key}",
                icon_custom_emoji_id=style.icon_custom_emoji_id,
            )
            for style in style_row
        ]
        for style_row in get_vinyl_style_rows()
    ]
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text=texts_module.BTN_DEV_SET_MENU_IMAGE,
                    callback_data="vinyl_menu_image:set",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✏️ تحرير النصوص (عربي)",
                    callback_data="dev_text:page:ar:0",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Edit Texts (English)",
                    callback_data="dev_text:page:en:0",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🛡️ القائمة البيضاء",
                    callback_data="dev_whitelist:open",
                )
            ],
            [
                InlineKeyboardButton(
                    text=texts_module.BTN_DEV_LIMITS_MENU,
                    callback_data="dev_limits:open",
                )
            ],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_whitelist_keyboard(user_ids: list[int]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"❌ إزالة {uid}",
                callback_data=f"dev_whitelist:remove:{uid}",
            )
        ]
        for uid in user_ids
    ]
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text="➕ إضافة مستخدم", callback_data="dev_whitelist:add"
                )
            ],
            [
                InlineKeyboardButton(
                    text=texts_module.BTN_BACK,
                    callback_data="dev_whitelist:back",
                )
            ],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_dev_limits_keyboard(
    color_choices: list[tuple[str, str]],
) -> InlineKeyboardMarkup:
    rows = []
    for value, text_var in color_choices:
        color_label = getattr(texts_module, text_var, value)
        is_paid = limits.is_premium_color(value)
        suffix = (
            texts_module.BTN_DEV_LIMITS_PAID_SUFFIX
            if is_paid
            else texts_module.BTN_DEV_LIMITS_FREE_SUFFIX
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{color_label} — {suffix}",
                    callback_data=f"dev_limits:toggle:{value}",
                    style="danger" if is_paid else "primary",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=texts_module.BTN_BACK,
                callback_data="dev_limits:back",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_dev_text_list_keyboard(
    page_names: list[str],
    *,
    page: int,
    lang: str,
    has_previous: bool,
    has_next: bool,
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=name,
                callback_data=f"dev_text:edit:{lang}:{name}",
            )
        ]
        for name in page_names
    ]
    nav_row = []
    if has_previous:
        nav_row.append(
            InlineKeyboardButton(
                text="◀️ السابق",
                callback_data=f"dev_text:page:{lang}:{page - 1}",
            )
        )
    if has_next:
        nav_row.append(
            InlineKeyboardButton(
                text="التالي ▶️",
                callback_data=f"dev_text:page:{lang}:{page + 1}",
            )
        )
    if nav_row:
        rows.append(nav_row)
    rows.append(
        [
            InlineKeyboardButton(
                text=texts_module.BTN_BACK,
                callback_data="dev_text:back",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_help_buttons_keyboard(
    buttons: list[dict[str, str]],
) -> InlineKeyboardMarkup | None:
    if not buttons:
        return None
    rows = [
        [InlineKeyboardButton(text=button["text"], url=button["url"])]
        for button in buttons
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_help_builder_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 نص الرسالة (Rich Msg)",
                    callback_data="help_builder:settext",
                )
            ],
            [
                InlineKeyboardButton(
                    text="➕ اضف زر",
                    callback_data="help_builder:addbtn",
                )
            ],
            [
                InlineKeyboardButton(
                    text="👁 معاينة",
                    callback_data="help_builder:preview",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💾 حفظ ونشر",
                    callback_data="help_builder:save",
                ),
                InlineKeyboardButton(
                    text="🔙 رجوع",
                    callback_data="help_builder:back",
                ),
            ],
        ]
    )


def build_help_root_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎛 تخصيص",
                    callback_data="help_builder:menu",
                )
            ]
        ]
    )
